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

import asyncio
import concurrent.futures
import functools

import vimba
import yaml

from .. import exposure
from . import basecamera

SECONDS_TO_MILLISECONDS = 1000
"Allied Vision cameras have timeouts in milliseconds."

SECONDS_TO_MICROSECONDS = 1000000
"Allied Vision camera have exposure times in microseconds."

IMAGE_TIMEOUT_PADDING = 200
"Additional time (ms) to add to the frame acquisition."


class AlliedVisionCamera(basecamera.BaseCamera):
    """Class for handling AlliedVision Vimba cameras."""

    def __init__(self, log=None):
        super().__init__(log=log)

        self.id = 0
        self.camera = None
        self.frame = None
        self.exposure_time = None
        self.is_live_exposure = False
        self.liveview_use_autoexposure = True
        self.normal_image_type = None
        self.lens_focal_length = None
        self.lens_diameter = None
        self.lens_aperture = None
        self.plate_scale = None
        self.loop = asyncio.get_running_loop()
        self.executor = concurrent.futures.ThreadPoolExecutor()

    @staticmethod
    def name():
        """Set camera name."""
        return "AlliedVision"

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : `str`
            The name of the configuration file to load.
        """
        self.id = config.config["id"]
        self.liveview_use_autoexposure = config.config["liveview_use_autoexposure"]
        self.normal_image_type = getattr(vimba.PixelFormat, config.config["image_type"])
        self.lens_focal_length = config.config["focal_length"]
        self.lens_diameter = config.config["diameter"]
        self.lens_aperture = config.config["aperture"]
        self.plate_scale = config.config["plate_scale"]

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
  liveview_use_autoexposure:
    default: true
    type: boolean
    description: Flag to set if live view uses autoexposure or exposure time from takeImages.
  image_type:
    type: string
    description: >
      The image type to store. This usually provides information about the
      pixel depth.
  focal_length:
    default: null
    anyOf:
      - type: number
      - type: "null"
    description: The focal length (mm) of the lens for the camera.
  diameter:
    default: null
    anyOf:
      - type: number
      - type: "null"
    description: The diameter (mm) of the lens for the camera.
  aperture:
    default: null
    anyOf:
      - type: string
      - type: "null"
    description: The aperture (f-stop) of the lens for the camera.
  plate_scale:
    default: null
    anyOf:
      - type: number
      - type: "null"
    description: The plate scale (arcsec/pixel) for the lens/camera setup.
"""
        )

    def get_make_and_model(self):
        """Get the make and model of the camera.

        Returns
        -------
        `str`
            The make and model of the camera.
        """
        return f"AlliedVision {self.camera.get_name()}"

    def get_roi(self):
        """Gets the region of interest.

        Returns
        -------
        `int`
            The top most pixel of the region.
        `int`
            The left most pixel of the region.
        `int`
            The width of the region in pixels.
        `int`
            The height of the region in pixels.
        """
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
        top : `int`
            The top most pixel of the region.
        left : `int`
            The left most pixel of the region.
        width : `int`
            The width of the region in pixels.
        height : `int`
            The height of the region in pixels.
        """
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
        the image can be encoded to JPEG.
        """
        self.is_live_exposure = True
        with vimba.Vimba.get_instance():
            with self.camera:
                self.camera.AcquisitionMode.set("SingleFrame")
                self.camera.ExposureAuto.set("Continuous")
                self.camera.set_pixel_format(vimba.PixelFormat.Mono8)
        super().start_live_view()

    def stop_live_view(self):
        """Stops an active live view data stream from the camera.

        This should review the image format back to original format.
        """
        self.is_live_exposure = False
        with vimba.Vimba.get_instance():
            with self.camera:
                self.camera.set_pixel_format(self.normal_image_type)
        super().stop_live_view()

    def _set_camera_exposure_time(self):
        """Set the exposure time on the camera."""
        with vimba.Vimba.get_instance():
            with self.camera:
                if not self.is_live_exposure or not self.liveview_use_autoexposure:
                    self.log.debug("Setting camera exposure time")
                    self.camera.ExposureAuto.set("Off")
                    self.camera.ExposureTimeAbs.set(
                        self.exposure_time * SECONDS_TO_MICROSECONDS
                    )

    async def start_take_image(self, exp_time, shutter, science, guide, wfs):
        """Start taking an image or a set of images.

        Parameters
        ----------
        exp_time : `float`
            The exposure time in seconds.
        shutter : `bool`
            Should the shutter be opened?
        science : `bool`
            Should the science/main sensor be used?
        guide : `bool`
            Should guider sensor be used?
        wfs : `bool`
            Should wave front sensor be used?
        """
        self.exposure_time = exp_time
        await self.loop.run_in_executor(self.executor, self._set_camera_exposure_time)
        await super().start_take_image(exp_time, shutter, science, guide, wfs)

    def _get_frame(self):
        """Wait for the frame to arrive from the camera.

        Returns
        -------
        frame : `Vimba.Frame`
            The frame captured from the camera.
        """
        with vimba.Vimba.get_instance():
            with self.camera:
                if self.liveview_use_autoexposure:
                    timeout_ms = int(
                        (self.camera.ExposureTimeAbs.get() / SECONDS_TO_MILLISECONDS)
                        + IMAGE_TIMEOUT_PADDING
                    )
                else:
                    timeout_ms = (
                        int(self.exposure_time) * SECONDS_TO_MILLISECONDS
                        + IMAGE_TIMEOUT_PADDING
                    )
                self.log.debug(f"Exposure timeout = {timeout_ms} ms")
                frame = self.camera.get_frame(timeout_ms=timeout_ms)
        return frame

    def _get_buffer_and_ancillary_data(self, frame):
        """Convert the frame and get the real exposure time.

        Parameters
        ----------
        frame : `Vimba.Frame`
            The frame from the camera.

        Returns
        -------
        buffer_array : `numpy.ndarray`
            The converted camera frame.
        actual_exp_time : `float`
            The actual frame exposure time (seconds).
        """
        with vimba.Vimba.get_instance():
            self.log.debug("Starting buffer conversion")
            buffer_array = frame.as_numpy_ndarray()
            self.log.debug(f"Finished converting buffer to {buffer_array.dtype}")
            anc_data = frame.get_ancillary_data()
            if anc_data:
                with anc_data:
                    actual_exp_time = anc_data.get_feature_by_name(
                        "ChunkExposureTime"
                    ).get()
            self.log.debug(
                f"Actual Exposure Time: {actual_exp_time / SECONDS_TO_MICROSECONDS} seconds"
            )
            self.log.debug("Finished getting ancillary data")
        return buffer_array, actual_exp_time

    async def end_integration(self):
        """End image integration."""
        self.log.debug("Start end_integration")
        self.frame = await self.loop.run_in_executor(self.executor, self._get_frame)
        await super().end_integration()

    async def end_readout(self):
        """Start reading out the image."""
        self.log.debug("Start end_readout")
        await super()._set_tag_values()
        buffer_array, actual_exp_time = await self.loop.run_in_executor(
            self.executor,
            functools.partial(self._get_buffer_and_ancillary_data, self.frame),
        )
        top, left, width, height = await self.loop.run_in_executor(
            self.executor, self.get_roi
        )
        self.log.debug("Finished getting ROI info")
        self.get_tag(name="TOP").value = top
        self.get_tag(name="LEFT").value = left
        self.get_tag(name="WIDTH").value = width
        self.get_tag(name="HEIGHT").value = height
        self.get_tag(name="EXPTIME").value = actual_exp_time / SECONDS_TO_MICROSECONDS
        self.log.debug("Finished setting header tags")
        image = exposure.Exposure(buffer_array, width, height, self.tags)
        await super().start_readout()
        self.log.debug("Finished creating exposure")
        return image

    def get_camera_info(self) -> dict:
        """Provide camera specific configuration for logevent_cameraInfo.

        Returns
        -------
        `dict`
            Dictionary of topic attribute name (key) and value for attribute.
            Example: {"lensDiameter": 50.0}
        """
        return {
            "lensFocalLength": self.lens_focal_length,
            "lensDiameter": self.lens_diameter,
            "lensAperture": self.lens_aperture,
            "plateScale": self.plate_scale,
        }
