.. py:currentmodule:: lsst.ts.genericcamera

.. _lsst.ts.genericcamera:

#####################
lsst.ts.genericcamera
#####################

ts_genericcamera contains the `GenericCameraCsc` and support code.

.. _lsst.ts.genericcamera-using:

Using lsst.ts.genericcamera
===========================

You can setup and build this package using eups and sconsUtils.
After setting up the package you can build it and run unit tests by typing ``pytest``.

Before running the CSC, a ``data`` directory needs to be created in the ``$HOME`` area of the user where the CSC process is being run.

To run the `GenericCamera` CSC type ``run_genericcamera <index>``

.. _lsst.ts.genericcamera-contributing:

Contributing
============

``lsst.ts.genericcamera`` is developed at https://github.com/lsst-ts/ts_genericcamera.
You can find Jira issues for this module under the `ts_genericcamera <https://jira.lsstcorp.org/issues/?jql=project%20%3D%20DM%20AND%20component%20%3D%20ts_genericcamera>`_ component.

.. If there are topics related to developing this module (rather than using it), link to this from a toctree placed here.

.. .. toctree::
..    :maxdepth: 1

.. _lsst.ts.genericcamera-pyapi:

Python API reference
====================

.. automodapi:: lsst.ts.genericcamera
   :no-main-docstr:
   :no-inheritance-diagram:
   :skip: find_library
   :skip: EarthLocation
   :skip: Time

Version History
===============

.. toctree::
    version_history
    :maxdepth: 1
