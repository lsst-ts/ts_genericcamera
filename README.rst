###################
ts_GenericCamera
###################

``ts_GenericCamera`` is a component of LSST Telescope and Site software.

``ts_GenericCamera`` implements the ``ts_GenericCamera`` CSC, which is responsible for
making the closed loop optical system.

The package is compatible with LSST DM's ``scons`` build system and ``eups`` package management system.
Assuming you have the basic LSST DM stack installed you can do the following, from within the package directory:

- ``setup -r .`` to setup the package and dependencies.
- ``scons`` to build the package (copy Python files from ``bin.src`` into ``bin`` after fixing the ``#!``) and run unit tests.
- ``scons install declare`` to install the package and declare it to eups.
- ``package-docs build`` to build the documentation.
  This requires ``documenteer``; see `building single package docs`_ for installation instructions.

.. _building single package docs: https://developer.lsst.io/stack/building-single-package-docs.html

This code uses ``pre-commit`` to maintain ``black`` formatting and ``flake8`` compliance.
To enable this:

* Run ``pre-commit install`` once.
* If directed, run ``git config --unset-all core.hooksPath`` once.
