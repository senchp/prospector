import time, sys, os
import numpy as np
np.errstate(invalid='ignore')

from prospect.models import model_setup
from prospect.io import write_results
from prospect import fitting
from prospect.likelihood import lnlike_spec, lnlike_phot, write_log
from dynesty.dynamicsampler import stopping_function, weight_function, _kld_error
from dynesty.utils import *

# --------------
# Read command line arguments
# --------------
sargv = sys.argv
argdict = {'param_file': ''}
clargs = model_setup.parse_args(sargv, argdict=argdict)
run_params = model_setup.get_run_params(argv=sargv, **clargs)

# --------------
# Globals
# --------------
# SPS Model instance as global
sps = model_setup.load_sps(**run_params)
# GP instances as global
spec_noise, phot_noise = model_setup.load_gp(**run_params)
# Model as global
global_model = model_setup.load_model(**run_params)
# Obs as global
global_obs = model_setup.load_obs(**run_params)

# -----------------
# LnP function as global
# ------------------

def lnprobfn(theta, model=None, obs=None, verbose=run_params['verbose']):
    """Given a parameter vector and optionally a dictionary of observational
    ata and a model object, return the ln of the posterior. This requires that
    an sps object (and if using spectra and gaussian processes, a GP object) be
    instantiated.

    :param theta:
        Input parameter vector, ndarray of shape (ndim,)

    :param model:
        bsfh.sedmodel model object, with attributes including ``params``, a
        dictionary of model parameters.  It must also have ``prior_product()``,
        and ``mean_model()`` methods defined.

    :param obs:
        A dictionary of observational data.  The keys should be
          *``wavelength``
          *``spectrum``
          *``unc``
          *``maggies``
          *``maggies_unc``
          *``filters``
          * and optional spectroscopic ``mask`` and ``phot_mask``.

    :returns lnp:
        Ln posterior probability.
    """
    if model is None:
        model = global_model
    if obs is None:
        obs = global_obs

    lnp_prior = model.prior_product(theta, nested=True)
    if np.isfinite(lnp_prior):
        # Generate mean model
        try:
            mu, phot, x = model.mean_model(theta, obs, sps=sps)
        except(ValueError):
            return -np.infty

        # Noise modeling
        if spec_noise is not None:
            spec_noise.update(**model.params)
        if phot_noise is not None:
            phot_noise.update(**model.params)
        vectors = {'spec': mu, 'unc': obs['unc'],
                   'sed': model._spec, 'cal': model._speccal,
                   'phot': phot, 'maggies_unc': obs['maggies_unc']}

        # Calculate likelihoods
        lnp_spec = lnlike_spec(mu, obs=obs, spec_noise=spec_noise, **vectors)
        lnp_phot = lnlike_phot(phot, obs=obs, phot_noise=phot_noise, **vectors)

        return lnp_phot + lnp_spec + lnp_prior
    else:
        return -np.infty


def prior_transform(u, model=None):
    if model is None:
        model = global_model
        
    return model.prior_transform(u)

    
# -----------------
# MPI pool.  This must be done *after* lnprob and
# chi2 are defined since slaves will only see up to
# sys.exit()
# ------------------
try:
    from emcee.utils import MPIPool
    pool = MPIPool(debug=False, loadbalance=True)
    nprocs = pool.size+1 # are we removing the master here?
    if not pool.is_master():
        # Wait for instructions from the master process.
        pool.wait()
        sys.exit(0)
except(ImportError, ValueError):
    pool = None
    nprocs = 1
    print('Not using MPI')


def halt(message):
    """Exit, closing pool safely.
    """
    print(message)
    try:
        pool.close()
    except:
        pass
    sys.exit(0)


if __name__ == "__main__":

    # --------------
    # Setup
    # --------------
    rp = run_params
    rp['sys.argv'] = sys.argv
    # Use the globals
    model = global_model
    obs = global_obs

    # Try to set up an HDF5 file and write basic info to it
    outroot = "{0}_{1}".format(rp['outfile'], int(time.time()))
    odir = os.path.dirname(os.path.abspath(outroot))
    if (not os.path.exists(odir)):
        print('Target output directory {} does not exist, please make it.'.format(odir))
        sys.exit(0)
    try:
        import h5py
        hfilename = outroot + '_mcmc.h5'
        hfile = h5py.File(hfilename, "a")
        print("Writing to file {}".format(hfilename))
        write_results.write_h5_header(hfile, run_params, model)
        write_results.write_obs_to_h5(hfile, obs)
    except(ImportError):
        hfile = None

    # -------
    # Sample
    # -------
    if rp['verbose']:
        print('dynesty sampling...')
    tstart = time.time()  # time it
    dynestyout = fitting.run_dynesty_sampler(lnprobfn, prior_transform, model.ndim,
                                             pool=pool, queue_size=nprocs, 
                                             stop_function=stopping_function,
                                             wt_function=weight_function,
                                             **rp)
    ndur = time.time() - tstart
    print('done dynesty in {0}s'.format(ndur))

    # -------------------------
    # Output pickles (and HDF5)
    # -------------------------
    
    # Write the dynesty result object as a pickle  
    import pickle
    with open(outroot + '_dns.pkl', 'w') as f:
        pickle.dump(dynestyout, f)
    partext = write_results.paramfile_string(**rp)
    
    # Write the model as a pickle
    write_results.write_model_pickle(outroot + '_model', model, powell=None,
                                     paramfile_text=partext)
    
    # Write HDF5
    if hfile is None:
        hfile = hfilename
    write_results.write_hdf5(hfile, rp, model, obs, dynestyout,
                             None, tsample=ndur)
