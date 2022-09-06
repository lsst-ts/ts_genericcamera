# This file is part of ts_genericcamera.
#
# Developed for the Vera Rubin Observatory Telescope and Site Systems.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import datetime
import io

from astropy.coordinates import EarthLocation
from astropy.time import Time
import gphoto2 as gp
import numpy as np
import rawpy
import yaml

from .. import exposure
from ..fits_header_items_generator import FitsHeaderItemsGenerator, FitsHeaderTemplate
from . import basecamera
from .. import utils


class CanonCamera(basecamera.BaseCamera):
    def __init__(self, log=None):
        super().__init__(log=log)
        self.id = None
        self.bin_value = None
        self.normal_image_type = None
        self.current_image_type = None
        self.width = None
        self.height = None
        self.iso = None
        self.cube_mnt = None
        self.quad_mnt = None

        self.camera = None
        self.exposure_time = None

        # The path to the image in the camera
        self.file_path = None

        # Add the Canon-related FITS header items to the generic ones.
        self.tags.append(
            FitsHeaderItemsGenerator().generate_fits_header_items(
                FitsHeaderTemplate.CANON
            )
        )

    @staticmethod
    def name():
        """Set camera name."""
        return "Canon"

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : str
            The name of the configuration file to load."""
        self.id = config.id
        self.bin_value = config.bin_value
        self.normal_image_type = config.image_type
        self.current_image_type = self.normal_image_type
        self.width = config.width
        self.height = config.height
        self.iso = config.iso
        self.cube_mnt = config.cube_mnt
        self.quad_mnt = config.quad_mnt

        # Initialize the camera. If not camera is detected then an Exception
        # will be raised.
        self.camera = gp.Camera()
        self.camera.init()

    def get_config_schema(self):
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for Canon cameras.
type: object
properties:
  id:
    default: 0
    type: number
    description: The ID of the camera to be set in the FITS header.
  bin_value:
    default: 1
    type: number
    description: The value for how to bin the image pixels.
  width:
    type: number
    default: 6744
    description: >
      The width of the sensor in pixels. This must match the full sensor width
      including the black point borders.
  height:
    type: number
    default: 4502
    description: >
      The height of the sensor in pixels. This must match the full sensor
      heigth including the black point borders.
  iso:
    type: number
    default: 200
  image_type:
    default: RAW
    type: string
    description: >
      The image type to store. This usually provides informtation about the
      pixel depth, the color space or whether it is a raw image of not.
    enum:
      - RAW
  cube_mnt:
    type: number
    decription: >
      The cubic distortion correction. This must be measured from an image.
    default: -0.069
  quad_mnt:
    type: number
    decription: >
      The quartic distortion correction. This must be measured from an image.
    default: 0.055
"""
        )

    def get_make_and_model(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        abilities = self.camera.get_abilities()
        return abilities.model

    def get_roi(self):
        """Gets the region of interest.

        Returns
        -------
        int
            The top most pixel of the region.
        int
            The left most pixel of the region.
        int
            The width of the region in pixels.
        int
            The height of the region in pixels."""
        return 0, 0, self.width, self.height

    async def start_take_image(self, exp_time, shutter, science, guide, wfs):
        """Start taking an image or a set of images.

        Parameters
        ----------
        exp_time : `float`
            The exposure time in seconds. If the value is at least 1 second
            then it gets rounded down to the nearest second since Canon cameras
            don't support floating point exposure times larger than or equal to
            1 second.
        shutter : `bool`
            Should the shutter be opened?
        science : `bool`
            Should the science/main sensor be used?
        guide : `bool`
            Should guider sensor be used?
        wfs : `bool`
            Should wave front sensor be used?
        """
        # Store the exposure time for later use
        if exp_time >= 1:
            exp_time = int(exp_time)
        self.exposure_time = exp_time
        # In order to be able to update the cameraq config via GPhoto, the
        # config object needs to be obtained ...
        cfg = self.camera.get_config()
        # ... the config parameters need to be adjusted ...
        cfg.get_child_by_name("focusmode").set_value("Manual")
        cfg.get_child_by_name("imageformat").set_value(self.normal_image_type)
        cfg.get_child_by_name("iso").set_value(str(self.iso))
        cfg.get_child_by_name("picturestyle").set_value("Standard")
        cfg.get_child_by_name("shutterspeed").set_value(str(self.exposure_time))
        # ... and the config needs to be written baqck to the camera
        self.camera.set_config(cfg, None)
        await super().start_take_image(exp_time, shutter, science, guide, wfs)

    async def start_integration(self):
        """Start integrating.

        This starts the exposure while obtaining the path to the file on the
        camera. The exposure will finish by itself because the camera
        controls that.
        """
        self.file_path = self.camera.capture(gp.GP_CAPTURE_IMAGE)
        await super().start_integration()

    async def end_readout(self):
        """End reading out the image.

        The image can be obtained by reading out the file_path variable in
        which the path to the file on the camera was stored.
        """
        camera_file = self.camera.file_get(
            self.file_path.folder, self.file_path.name, gp.GP_FILE_TYPE_NORMAL
        )
        # Load the image data
        file_data = camera_file.get_data_and_size()

        # Convert to a numpy array
        raw = rawpy.RawPy()
        raw.open_buffer(io.BytesIO(file_data))
        raw.unpack()
        rgb = raw.postprocess(
            no_auto_bright=True, use_auto_wb=False, gamma=(1, 1), output_bps=16
        )
        # Use luminosity conversion to get 16 bit B/W image. See
        # https://stackoverflow.com/a/51571053
        luminance = np.dot(rgb[..., :3], [0.299, 0.587, 0.114])

        # Remove the image from the camera
        del camera_file
        raw.close()

        await self._set_tag_values()

        image = exposure.Exposure(luminance, self.width, self.height, self.tags, False)
        return image

    async def _set_tag_values(self):
        """Convenience coroutine to provide values for all the tags in the FITS
        header."""
        # ---- Date, night and basic image information ----
        now_string = datetime.datetime.now(tz=datetime.timezone.utc).strftime(
            utils.DATETIME_FORMAT
        )
        date_obs = self.datetime_start_readout.strftime(utils.DATE_FORMAT)
        date_beg = self.datetime_start_readout.strftime(utils.DATETIME_FORMAT)
        date_end = self.datetime_end_readout.strftime(utils.DATETIME_FORMAT)
        self.get_tag(name="DATE").value = now_string
        self.get_tag(name="DATE-OBS").value = date_obs
        self.get_tag(name="DATE-BEG").value = date_beg
        self.get_tag(name="DATE-END").value = date_end
        self.get_tag(name="MJD").value = Time(now_string, format="mjd").value
        self.get_tag(name="MJD-OBS").value = Time(date_obs, format="mjd").value
        self.get_tag(name="MJD-BEG").value = Time(date_beg, format="mjd").value
        self.get_tag(name="MJD-END").value = Time(date_end, format="mjd").value
        # TODO Not sure what value to set here.
        self.get_tag(name="OBSID").value = ""
        self.get_tag(name="IMGTYPE").value = "OBJECT"

        # ---- Pointing info, etc. ----
        # Always pointing at the zenith.
        elevation = 90.0
        # Minor axis always points south
        azimuth = 0.0

        # Retrieve observing location info
        lon = next((tag for tag in self.tags if tag.name == "OBS-LONG")).value
        lat = next((tag for tag in self.tags if tag.name == "OBS-LAT")).value
        height = next((tag for tag in self.tags if tag.name == "OBS-ELEV")).value
        # Create EarthLocation instance for Rubin Observatory
        rubin = EarthLocation.from_geodetic(lon=lon, lat=lat, height=height)

        radec_start = self.__get_radec_from_altaz_location_time(
            alt=elevation, az=azimuth, obs_time=date_beg, location=rubin
        )
        radec_end = self.__get_radec_from_altaz_location_time(
            alt=elevation, az=azimuth, obs_time=date_end, location=rubin
        )
        self.get_tag(name="RASTART").value = radec_start.ra.value
        self.get_tag(name="DECSTART").value = radec_start.dec.value
        self.get_tag(name="RAEND").value = radec_end.ra.value
        self.get_tag(name="DECEND").value = radec_end.dec.value
        # Rotation for AllsSky camera is assumed to always be zero.
        self.get_tag(name="ROTPA").value = 0
        # Can be the same as azimuth since only the unit differs.
        self.get_tag(name="HASTART").value = azimuth
        self.get_tag(name="EL").value = elevation
        self.get_tag(name="AZ").value = azimuth
        # Can be the same as azimuth since only the unit differs.
        self.get_tag(name="HAEND").value = azimuth
        self.get_tag(name="RADESYS").value = "ICRS"
        # This value was measured.
        self.get_tag(name="CUBE-MNT").value = self.cube_mnt
        # This value was measured.
        self.get_tag(name="QUAD-MNT").value = self.quad_mnt

        # ---- Image-identifying used to build OBS-ID ----
        self.get_tag(name="CAMCODE").value = f"AllSkyCam_{self.name()}_{self.id}"
        # TODO Not sure what value to set here.
        self.get_tag(name="DAYOBS").value = ""
        # TODO Not sure what value to set here.
        self.get_tag(name="SEQNUM").value = ""
        self.get_tag(name="IMGTYPE").value = "OBS"

        # ---- Information from Camera ----
        self.get_tag(name="APERTURE").value = "F/4"
        self.get_tag(name="FLEN").value = 8.0

        # ---- Geometry from Camera ----
        self.get_tag(name="DETSIZE").value = "36 x 24"
        # Pixel size = 5.36 micrometer, focal length = 8.0 mm
        self.get_tag(name="SECPIX").value = (5.36 / 8.0) * 206.265

        # ---- Exposure-related information ----
        self.get_tag(name="EXPTIME").value = self.exposure_time
        self.get_tag(name="ISO").value = self.iso
