# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import absolute_import, division, print_function
import copy
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.ndimage.interpolation import spline_filter
from scipy.ndimage.interpolation import shift
import astropy.io.fits as pyfits
import fermipy.utils as utils
import fermipy.wcs_utils as wcs_utils


class MapInterpolator(object):
    """Object that can efficiently generate source maps by
    interpolation of a map object."""

    def __init__(self, data, pix_ref, npix, rebin):


        self._shape = data.shape
        self._data = data
        self._data_spline = []
        for i in range(data.shape[0]):
            self._data_spline += [spline_filter(self._data[i], order=2)]

        self._axes = []
        for i in range(data.ndim):
            self._axes += [np.arange(0, data.shape[i], dtype=float)]

        #self._coords = np.meshgrid(*self._axes[1:], indexing='ij')
        self._rebin = rebin
        self._npix = npix

        self._shape_out = (np.array(self.shape)/float(rebin)).astype(int)
        
        # Reference pixel in output coordinates
        self._pix_ref = pix_ref

    @property
    def data(self):
        return self._data

    @property
    def shape(self):
        return self._shape

    @property
    def shape_out(self):
        return self._shape_out
    
    @property
    def rebin(self):
        return self._rebin
    
    def get_offsets(self, pix):
        """Get offset of the first pixel in each dimension in the
        global coordinate system."""
        
        idx = []
        for i in range(len(self.shape)):

            if i == 0:
                idx += [0]
                continue
            
            npix1 = self.shape_out[i]
            ipix = int(pix[i-1])            
            ipix = ipix - max(0,npix1//2 - self._npix + ipix)
            idx += [max(ipix - npix1//2,0)]

            #xref = pix[i-1]
            #npix0 = self._npix            
            #print('here',idx[i],max(int(xref) - max(0,npix1//2 - npix0 + int(xref)) - npix1//2,0))

        return idx
            
    def get_slices(self, pix):

        idx = self.get_offsets(pix)

        slices = []
        for i, t in enumerate(idx):
            if i == 0:
                slices += [slice(None)]
            else:
                slices += [slice(t,t + self.shape_out[i])]

        return slices

    def shift_to_coords(self, pix):
        """Create a new map that is shifted to the pixel coordinates
        ``pix``."""

        pix_offset = self.get_offsets(pix)

        # Calculate the offset in pixel coordinates that should be
        # applied
        dpix = np.zeros(len(self.shape)-1)
        for i in range(len(self.shape)-1):

            x = self.rebin*(pix[i] - pix_offset[i+1]) + (self.rebin-1.0)/2.
            
            print(i, pix[i], x, pix_offset[i+1], self._pix_ref[i])


            dpix[i] = x - self._pix_ref[i]
            #dpix[i] = self.rebin * (pix[i] - pix_offset[i+1] - self._pix_ref[i])

        print(pix_offset, dpix, self._pix_ref)
            
        k = np.zeros(self._data.shape)
        for i in range(k.shape[0]):
            k[i] = shift(self._data_spline[i], dpix, cval=0.0,
                         order=2, prefilter=False)

        for i in range(1,len(self.shape)):            
            k = utils.sum_bins(k, i, self.rebin)

        return k


class SourceMapCache(object):
    """Object that can efficiently generate source maps by
    interpolation of a map object."""

    def __init__(self, m0, m1):
        self._m0 = m0
        self._m1 = m1

    def create_map(self, pix):
        """Create a new map that is shifted to the pixel coordinates
        ``pix``."""

        k0 = self._m0.shift_to_coords(pix)
        k1 = self._m1.shift_to_coords(pix)

        s1 = self._m1.get_slices(pix)

        k0[s1] = k1
        
        return k0

        m.data[self._m1.slices] = self._m1.shift_to_coords(pix)

        return k

        coords = copy.deepcopy(self._coords)
        dpix = np.zeros(2)
        for i in range(len(coords)):
            coords[i] -= self._rebin * pix[i] - self._pix_ref[i]
            dpix[i] = self._rebin * pix[i] - self._pix_ref[i]

        k = np.zeros(self._data.shape)
        k2 = np.zeros(self._data.shape)

        import time

        t0 = time.time()
        for i in range(k.shape[0]):
            k[i] = map_coordinates(self._data_spline[i], coords, cval=0.0,
                                   order=2, prefilter=False)
        t1 = time.time()
        print(t1 - t0)

        t0 = time.time()
        for i in range(k.shape[0]):
            k2[i] = shift(self._data_spline[i], dpix, cval=0.0,
                          order=1, prefilter=False)
        t1 = time.time()
        print(t1 - t0)

        k = utils.sum_bins(k, 1, self._rebin)
        k = utils.sum_bins(k, 2, self._rebin)
        k2 = utils.sum_bins(k2, 1, self._rebin)
        k2 = utils.sum_bins(k2, 2, self._rebin)

        return k, k2

    @staticmethod
    def create(psf, spatial_model, spatial_width, npix, cdelt,
               rebin=4):

        xpix = (npix - 1.0) / 2.
        ypix = (npix - 1.0) / 2.
        pix_ref = np.array([ypix, xpix])
        pix_pad = np.array([0.0, 0.0])

        k0 = make_srcmap(psf, spatial_model, spatial_width,
                         npix=npix,
                         xpix=xpix, ypix=ypix,
                         cdelt=cdelt,
                         rebin=1)

        m0 = MapInterpolator(k0, pix_ref, 1)

        npix1 = 10 * rebin
        xpix1 = (npix1 - 1.0) / 2.
        ypix1 = (npix1 - 1.0) / 2.

        k1 = make_srcmap(psf, spatial_model, spatial_width,
                         npix=npix1,
                         xpix=xpix1, ypix=ypix1,
                         cdelt=cdelt / rebin,
                         rebin=1)

        pix_pad = np.array([npix / 2 - 10, npix / 2 - 10])

        m1 = MapInterpolator(k1, pix_ref, pix_pad, rebin)

        return SourceMapCache(m0, m1)


def make_srcmap(psf, spatial_model, sigma, npix=500, xpix=0.0, ypix=0.0,
                cdelt=0.01, rebin=1, psf_scale_fn=None):
    """Compute the source map for a given spatial model.

    Parameters
    ----------

    skydir : `~astropy.coordinates.SkyCoord`

    psf : `~fermipy.irfs.PSFModel`

    spatial_model : str
        Spatial model.

    sigma : float
        Spatial size parameter for extended models.

    xpix : float
        Source position in pixel coordinates in X dimension.

    ypix : float
        Source position in pixel coordinates in Y dimension.

    rebin : int    
        Factor by which the original map will be oversampled in the
        spatial dimension when computing the model.

    psf_scale_fn : callable        
        Function that evaluates the PSF scaling function.
        Argument is energy in MeV.

    """

    energies = psf.energies
    nebin = len(energies)

    if spatial_model == 'GaussianSource' or spatial_model == 'RadialGaussian':
        k = utils.make_cgauss_kernel(psf, sigma, npix * rebin, cdelt / rebin,
                                     xpix * rebin, ypix * rebin,
                                     psf_scale_fn)
    elif spatial_model == 'DiskSource' or spatial_model == 'RadialDisk':
        k = utils.make_cdisk_kernel(psf, sigma, npix * rebin, cdelt / rebin,
                                    xpix * rebin, ypix * rebin,
                                    psf_scale_fn)
    elif spatial_model == 'PSFSource' or spatial_model == 'PointSource':
        k = utils.make_psf_kernel(psf, npix * rebin, cdelt / rebin,
                                  xpix * rebin, ypix * rebin,
                                  psf_scale_fn)
    else:
        raise Exception('Unsupported spatial model: %s' % spatial_model)

    if rebin > 1:
        k = utils.rebin_map(k, nebin, npix, rebin)

    k *= psf.exp[:, np.newaxis, np.newaxis] * np.radians(cdelt) ** 2

    return k


def make_cgauss_mapcube(skydir, psf, sigma, outfile, npix=500, cdelt=0.01,
                        rebin=1):
    energies = psf.energies
    nebin = len(energies)

    k = utils.make_cgauss_kernel(psf, sigma, npix * rebin, cdelt / rebin)

    if rebin > 1:
        k = utils.rebin_map(k, nebin, npix, rebin)
    w = wcs_utils.create_wcs(skydir, cdelt=cdelt,
                             crpix=npix / 2. + 0.5, naxis=3)

    w.wcs.crpix[2] = 1
    w.wcs.crval[2] = 10 ** energies[0]
    w.wcs.cdelt[2] = energies[1] - energies[0]
    w.wcs.ctype[2] = 'Energy'

    ecol = pyfits.Column(name='Energy', format='D', array=10 ** energies)
    hdu_energies = pyfits.BinTableHDU.from_columns([ecol], name='ENERGIES')

    hdu_image = pyfits.PrimaryHDU(np.zeros((nebin, npix, npix)),
                                  header=w.to_header())

    hdu_image.data[...] = k

    hdu_image.header['CUNIT3'] = 'MeV'

    hdulist = pyfits.HDUList([hdu_image, hdu_energies])
    hdulist.writeto(outfile, clobber=True)


def make_psf_mapcube(skydir, psf, outfile, npix=500, cdelt=0.01, rebin=1):
    energies = psf.energies
    nebin = len(energies)

    k = utils.make_psf_kernel(psf, npix * rebin, cdelt / rebin)

    if rebin > 1:
        k = utils.rebin_map(k, nebin, npix, rebin)
    w = wcs_utils.create_wcs(skydir, cdelt=cdelt,
                             crpix=npix / 2. + 0.5, naxis=3)

    w.wcs.crpix[2] = 1
    w.wcs.crval[2] = 10 ** energies[0]
    w.wcs.cdelt[2] = energies[1] - energies[0]
    w.wcs.ctype[2] = 'Energy'

    ecol = pyfits.Column(name='Energy', format='D', array=10 ** energies)
    hdu_energies = pyfits.BinTableHDU.from_columns([ecol], name='ENERGIES')

    hdu_image = pyfits.PrimaryHDU(np.zeros((nebin, npix, npix)),
                                  header=w.to_header())

    hdu_image.data[...] = k

    hdu_image.header['CUNIT3'] = 'MeV'

    hdulist = pyfits.HDUList([hdu_image, hdu_energies])
    hdulist.writeto(outfile, clobber=True)


def make_gaussian_spatial_map(skydir, sigma, outfile, cdelt=None, npix=None):

    if cdelt is None:
        cdelt = sigma / 10.

    if npix is None:
        npix = int(np.ceil((6.0 * (sigma + cdelt)) / cdelt))

    w = wcs_utils.create_wcs(skydir, cdelt=cdelt, crpix=npix / 2. + 0.5)
    hdu_image = pyfits.PrimaryHDU(np.zeros((npix, npix)),
                                  header=w.to_header())

    hdu_image.data[:, :] = utils.make_gaussian_kernel(sigma, npix=npix,
                                                      cdelt=cdelt)
    hdulist = pyfits.HDUList([hdu_image])
    hdulist.writeto(outfile, clobber=True)


def make_disk_spatial_map(skydir, radius, outfile, cdelt=None, npix=None):

    if cdelt is None:
        cdelt = radius / 10.

    if npix is None:
        npix = int(np.ceil((2.0 * (radius + cdelt)) / cdelt))

    w = wcs_utils.create_wcs(skydir, cdelt=cdelt, crpix=npix / 2. + 0.5)
    hdu_image = pyfits.PrimaryHDU(np.zeros((npix, npix)),
                                  header=w.to_header())

    hdu_image.data[:, :] = utils.make_disk_kernel(radius, npix=npix,
                                                  cdelt=cdelt)
    hdulist = pyfits.HDUList([hdu_image])
    hdulist.writeto(outfile, clobber=True)


def delete_source_map(srcmap_file, names, logger=None):
    """Delete a map from a binned analysis source map file if it exists.

    Parameters
    ----------
    srcmap_file : str
       Path to the source map file.

    names : list
       List of HDU keys of source maps to be deleted.

    """
    hdulist = pyfits.open(srcmap_file)
    hdunames = [hdu.name.upper() for hdu in hdulist]

    if not isinstance(names, list):
        names = [names]

    for name in names:
        if not name.upper() in hdunames:
            continue
        del hdulist[name.upper()]

    hdulist.writeto(srcmap_file, clobber=True)


def update_source_maps(srcmap_file, srcmaps, logger=None):
    hdulist = pyfits.open(srcmap_file)
    hdunames = [hdu.name.upper() for hdu in hdulist]

    for name, data in srcmaps.items():

        if not name.upper() in hdunames:

            for hdu in hdulist[1:]:
                if hdu.header['XTENSION'] == 'IMAGE':
                    break

            newhdu = pyfits.ImageHDU(data, hdu.header, name=name)
            newhdu.header['EXTNAME'] = name
            hdulist.append(newhdu)

        if logger is not None:
            logger.debug('Updating source map for %s' % name)

        hdulist[name].data[...] = data

    hdulist.writeto(srcmap_file, clobber=True)
