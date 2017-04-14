"""Contains functions for making a whitematter mask
"""
import shutil
import tempfile
import subprocess as sp

import numpy as np
import nibabel

#from . import utils
from .database import db
from .options import config
from .xfm import Transform

fsl_prefix = config.get('basic', 'fsl_prefix')


def brainmask(outfile, subject):
    raw = db.get_anat(subject, type='raw').get_filename()
    print('Brain masking anatomical...')
    cmd = '{fsl_prefix}bet {raw} {bet} -B -v'.format(fsl_prefix=fsl_prefix, raw=raw, bet=outfile)
    assert sp.call(cmd, shell=True) == 0, "Error calling fsl-bet"

def whitematter(outfile, subject, do_voxelize=False):
    try:
        if not do_voxelize:
            raise IOError
        else:
            voxelize(outfile, subject, surf="wm")
    except IOError:
        bet = db.get_anat(subject, type='brainmask').get_filename()
        try:
            cache = tempfile.mkdtemp()
            print("Segmenting the brain...")
            cmd = '{fsl_prefix}fast -o {cache}/fast {bet}'.format(fsl_prefix=fsl_prefix, cache=cache, bet=bet)
            assert sp.call(cmd, shell=True) == 0, "Error calling fsl-fast"

            wmfl = 'fast_pve_2'
            arr = np.asarray(nibabel.load('{cache}/{wmseg}.nii.gz'.format(cache=cache,wmseg=wmfl)).get_data())
            if arr.sum() == 0:
                from warnings import warn
                warn('"fsl-fast" with default settings failed. Trying no pve, no bias correction...')
                cmd = '{fsl_prefix}fast -g --nopve --nobias -o {cache}/fast {bet}'.format(fsl_prefix=fsl_prefix, cache=cache, bet=bet)
                assert sp.call(cmd, shell=True) == 0, "Error calling fsl-fast"
                wmfl = 'fast_seg_2'

            cmd = '{fsl_prefix}fslmaths {cache}/{wmfl} -thr 0.5 -bin {out}'.format(fsl_prefix=fsl_prefix, cache=cache, wmfl=wmfl, out=outfile)
            assert sp.call(cmd, shell=True) == 0, 'Error calling fsl-maths'

            # check generated mask succeeded
            arr = np.asarray(nibabel.load('{outfl}'.format(outfl=outfile)).get_data())
            assert arr.sum() >= 0, 'Error with generated whitematter mask.'

        finally:
            shutil.rmtree(cache)

def voxelize(outfile, subject, surf='wm', mp=True):
    '''Voxelize the whitematter surface to generate the white matter mask'''
    from . import polyutils
    nib = db.get_anat(subject, "raw")
    shape = nib.get_shape()
    vox = np.zeros(shape, dtype=bool)
    for pts, polys in db.get_surf(subject, surf, nudge=False):
        xfm = Transform(np.linalg.inv(nib.get_affine()), nib)
        vox += polyutils.voxelize(xfm(pts), polys, shape=shape, center=(0,0,0), mp=mp).astype('bool')
        
    nib = nibabel.Nifti1Image(vox, nib.get_affine(), header=nib.get_header())
    nib.to_filename(outfile)

    return vox.T
