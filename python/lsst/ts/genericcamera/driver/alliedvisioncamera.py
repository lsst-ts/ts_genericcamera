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

import vimba
import yaml

from . import basecamera
from .. import exposure
from ..fits_header_items_generator import FitsHeaderItemsGenerator, FitsHeaderTemplate

MILLISECONDS = 10**3
"Allied Vision cameras have timeouts in milliseconds."

MICROSECONDS = 10**6
"Allied Vision camera have exposure times in microseconds."


class AlliedVisionCamera(basecamera.BaseCamera):
    def __init__(self, log=None):
        super().__init__(log=log)

        self.id = 0
        self.camera = None
        self.frame = None
        self.exposure_time = None
        self.done_init = False
        self.is_live_exposure = False

        self.tags = FitsHeaderItemsGenerator().generate_fits_header_items(
            FitsHeaderTemplate.STARTRACKER
        )
        self.log.debug(f"Tags: {self.tags}")

    @staticmethod
    def name():
        """Set camera name."""
        return "AlliedVision"

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : str
            The name of the configuration file to load."""
        self.id = config.config["id"]

        with vimba.Vimba.get_instance() as v:
            self.camera = v.get_camera_by_id(self.id)
            with self.camera:
                # Try to adjust GeV packet size.
                # This Feature is only available for GigE - Cameras.
                try:
                    self.camera.GVSPAdjustPacketSize.run()
                    while not self.camera.GVSPAdjustPacketSize.is_done():
                        pass
                except (AttributeError, vimba.VimbaFeatureError):
                    self.log.warning(
                        "Camera is not GigE or packet size adjustment failed."
                    )
                # Try to enable ChunkMode
                try:
                    self.camera.ChunkModeActive.set(True)
                except (AttributeError, vimba.VimbaFeatureError):
                    self.log.warning("ChunkMode not available.")

    def get_config_schema(self):
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for Allied Vision cameras.
type: object
properties:
  id:
    default: DEV
    type: string
    description: The ID of the camera to be set in the FITS header.
  bin_value:
    default: 1
    type: number
    description: The value for how to bin the image pixels.
"""
        )

    def get_make_and_model(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        return self.camera.get_name()

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
        with vimba.Vimba.get_instance():
            with self.camera:
                left = self.camera.OffsetX.get()
                top = self.camera.OffsetY.get()
                width = self.camera.Width.get()
                height = self.camera.Height.get()
        return top, left, width, height

    def set_roi(self, top, left, width, height):
        """Sets the region of interest.

        Parameters
        ----------
        top : int
            The top most pixel of the region.
        left : int
            The left most pixel of the region.
        width : int
            The width of the region in pixels.
        height : int
            The height of the region in pixels."""
        with vimba.Vimba.get_instance():
            with self.camera:
                self.camera.OffsetX.set(left)
                self.camera.OffsetY.set(top)
                self.camera.Width.set(width)
                self.camera.Height.set(height)

    def set_full_frame(self):
        """Sets the region of interest to the whole sensor."""
        with vimba.Vimba.get_instance():
            with self.camera:
                self.set_roi(
                    0, 0, self.camera.WidthMax.get(), self.camera.HeightMax.get()
                )

    def start_live_view(self):
        """Configure the camera for live view.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""

        self.is_live_exposure = True
        with vimba.Vimba.get_instance():
            with self.camera:
                self.camera.AcquisitionMode.set("SingleFrame")
                self.camera.ExposureAuto.set("Continuous")
                self.camera.set_pixel_format(vimba.PixelFormat.Mono8)
        super().start_live_view()

    def stop_live_view(self):
        """Stops an active live view data stream from the camera.

        This should review the image format back to original format."""
        self.is_live_exposure = False
        with vimba.Vimba.get_instance():
            with self.camera:
                self.camera.set_pixel_format(vimba.PixelFormat.Mono12)
        super().stop_live_view()

    async def start_take_image(self, exp_time, shutter, science, guide, wfs):
        """Start taking an image or a set of images.

        Parameters
        ----------
        exp_time : float
            The exposure time in seconds.
        shutter : bool
            Should the shutter be opened?
        science : bool
            Should the science/main sensor be used?
        guide : bool
            Should guider sensor be used?
        wfs : bool
            Should wave front sensor be used?
        """
        self.exposure_time = exp_time
        with vimba.Vimba.get_instance():
            with self.camera:
                if not self.is_live_exposure:
                    self.camera.ExposureAuto.set("Off")
                    self.camera.ExposureTimeAbs.set(self.exposure_time * MICROSECONDS)
        await super().start_take_image(exp_time, shutter, science, guide, wfs)

    async def end_readout(self):
        """Start reading out the image."""
        with vimba.Vimba.get_instance():
            # v.enable_log(vimba.LOG_CONFIG_INFO)
            with self.camera:
                timeout = int(self.exposure_time + 2)
                self.log.info(f"Exposure timeout = {timeout} seconds")
                frame = self.camera.get_frame(timeout_ms=timeout * MILLISECONDS)
                buffer_array = frame.as_numpy_ndarray()
                anc_data = frame.get_ancillary_data()
                if anc_data:
                    with anc_data:
                        actual_exp_time = anc_data.get_feature_by_name(
                            "ChunkExposureTime"
                        ).get()
                self.log.info(
                    f"Actual Exposure Time: {actual_exp_time / MICROSECONDS} seconds"
                )
        top, left, width, height = self.get_roi()

        self.get_tag(name="TOP").value = top
        self.get_tag(name="LEFT").value = left
        self.get_tag(name="WIDTH").value = width
        self.get_tag(name="HEIGHT").value = height
        self.get_tag(name="EXPTIME").value = actual_exp_time / MICROSECONDS

        await super().start_readout()
        image = exposure.Exposure(buffer_array, width, height, self.tags)
        return image
