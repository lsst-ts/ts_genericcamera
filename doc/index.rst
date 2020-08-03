.. py:currentmodule:: lsst.ts.GenericCamera

.. _lsst.ts.GenericCamera:

########################
lsst.ts.GenericCamera
########################

ts_GenericCamera contains the `GenericCameraCsc` and suport code.

.. _lsst.ts.GenericCamera-using:

Using lsst.ts.GenericCamera
==============================

You can setup and build this package using eups and sconsUtils.
After setting up the package you can build it and run unit tests by typing ``scons``.
Building it merely copies ``bin.src/run_genericcamera.py`` into ``bin/`` after tweaking the ``#!`` line.

To run the `GenericCamera` CSC type ``run_genericcamera.py``

.. _lsst.ts.GenericCamera-contributing:

Contributing
============

``lsst.ts.GenericCamera`` is developed at https://github.com/lsst-ts/ts_GenericCamera.
You can find Jira issues for this module under the `ts_GenericCamera <https://jira.lsstcorp.org/issues/?jql=project%20%3D%20DM%20AND%20component%20%3D%20ts_GenericCamera>`_ component.

.. If there are topics related to developing this module (rather than using it), link to this from a toctree placed here.

.. .. toctree::
..    :maxdepth: 1

.. _lsst.ts.GenericCamera-pyapi:

Python API reference
====================

.. automodapi:: lsst.ts.GenericCamera
   :no-main-docstr:
   :no-inheritance-diagram:
