.. py:currentmodule:: lsst.ts.genericcamera

.. _lsst.ts.ess.version_history:

###############
Version History
###############

v1.3.0
======

* Pass camera information through cameraInfo event
* Streaming mode handling stubs added but no implementation

v1.2.2
======

* Fix handling of null values from header to be None rather than empty string
* Make repo use ts-pre-commit-config methodology for pre-commit configuration

v1.2.1
======

* Fix image source definition

v1.2.0
======

* Add two new configuration parameters; ``always_save`` and ``directory``.

v1.1.0
======

* Fixed bug in AlliedVisionCamera class
* Made CanonCamera driver optional
* Updated package dependencies

v1.0.0
======

* Add LFA file saving capability
* Timestamps are now TAI
* Populate events with information necessary for GCHeaderService
* Standardize image name with image name service
* Use GCHeaderService for image header information

v0.7.0
======

* Add AlliedVision camera driver

v0.6.0
======

* Switch to pyproject.toml.

Requires:

* ts_salobj 7
* ts_idl 4.0
* IDL file for GenericCamera from ts_xml 12

v0.5.0
======

* Prepare for salobj 7.
* Rename the GenericCamera base class to BaseCamera.
* Replace camelCase names with snake_case where appropriate.

Requires:

* ts_salobj 7
* ts_idl 3.1
* IDL file for GenericCamera from ts_xml 11

v0.4.0
======

* Renamed to ts_genericcamera.
* Renamed the top Python module to lsst.ts.genericcamera.
* Added an auto exposure infrastructure.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for GenericCamera from ts_xml 10.0

v0.3.2
======

* Updated the conda recipe for noarch.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for GenericCamera from ts_xml 9.0


v0.3.1
======

* The conda package now will be built for noarch.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for GenericCamera from ts_xml 9.0


v0.3.0
======

* Added FITS header code.

Requires:

* ts_salobj 6.3
* ts_idl 3.1
* IDL file for GenericCamera from ts_xml 9.0


v0.2.0
======

Added Canon camera support.

Requires:

* ts_salobj 6.3
* ts_idl 3.0
* IDL file for GenericCamera from ts_xml 8.0


v0.1.0
======

First release of the GenericCamera CSC.

This version already includes some useful things:

* A functioning CSC which can command several types of cameras.
