The Model
=========

Parameter specification
-------------------------------

All model parameters require a specification in the parameters file.
For a single parameter the specification is a dictionary that must at minimum include several keys:

``"name", "N", "init", "isfree"``

Parameters with ``"isfree": True`` will be varied during the optimization and sampling.
For these parameters the following additional keys of the dictionary are required:
``"prior_function"`` and ``"prior_args"``
with values consisting of a the prior function (e.g. ``tophat``) and a dictionary of arguments to the prior function (e.g. ``"mini":0, "maxi":100``).
Prior functions can be found in the ``priors`` module.

It's also a good idea to have a ``"units"`` key, a string describing the units of the the parameter.


The ``model_params`` List
-------------------------------------

This is simply a list of dictionaries describing the model parameters.
It is passed to the ``ProspectorParams`` object on initialization.
The free parameters will be varied by the code during the optimization and sampling phases.
The initial value from which optimization is begun is set by the ``"init"`` values of each parameter.
For fixed parameters the ``"init"`` value gives the value of that parameter to use throughout the optimization and MCMC phases
(unless the ``"depends_on"`` key is present, see Advanced_.)

Nearly all parameters used by FSPS can be set (or varied) here.
The default FSPS parameter values will be used unless specified in a fixed parameter,
e.g. ``imf_type`` can be changed by including it as a fixed parameter with value given by ``"init"``.
More generally any parameter used by the source basis object to build an SED can be in the ``model_params`` list.


The ``load_model()`` method
------------------------------------------

This should return an instance of a subclass of the ``bsfh.models.ProspectorParams`` object.
It is given the ``run_params`` dictionary as an argument list,
so the model can be modified based on keywaords given there (or at the command line).


The ``load_sps()`` function
-------------------------------------

The likelihood function and SED models take a source basis (``sps``) object as an argument.
This object should be returned by the ``load_sps()`` function in the **parameter file**.
The source basis object generally includes all the spectral libraries necessary to build a model,
as well as some model building code.
This object is defined globally to enable multiprocessing, since generally it can't (or shouldn't) be serialized
and sent to other processors.


The ``load_gp()`` function
-------------------------------------

This function should return a GaussianProcess object for the
spectroscopy or photometry. Either or both can be ``None`` in which case
the likelihood will not include covariant noise.