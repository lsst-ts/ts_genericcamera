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

__all__ = ["GenericCameraCsc"]

import asyncio
import inspect
import logging
import os

# TODO Use utils.current_tai() instead.
import time
import traceback
import types

import numpy as np
import yaml

from .config_schema import CONFIG_SCHEMA
from . import __version__
from lsst.ts import salobj

from .liveview import liveview
from . import driver


LV_ERROR = 1000
"""Error code for when the live view loop dies and the CSC is in enable
state.
"""

AE_ERROR = 2000
"""Error code for when the auto exposure loop dies and the CSC is in
enable state.
"""


class GenericCameraCsc(salobj.ConfigurableCsc):

    valid_simulation_modes = (0,)
    version = __version__

    def __init__(
        self,
        index,
        config_dir=None,
        initial_state=salobj.State.STANDBY,
        simulation_mode=0,
    ):
        super().__init__(
            "GenericCamera",
            index=index,
            config_schema=CONFIG_SCHEMA,
            config_dir=config_dir,
            initial_state=initial_state,
            simulation_mode=simulation_mode,
        )

        ch = logging.StreamHandler()
        console_format = (
            "%(asctime)s - %(levelname)s - %(name)s [%(filename)s:%(lineno)d]: "
            "%(message)s"
        )
        ch.setFormatter(logging.Formatter(console_format))
        self.log.addHandler(ch)

        # Create dictionary of camera options.
        self.drivers = {}
        for member in inspect.getmembers(driver):
            is_class = inspect.isclass(member[1])
            is_subclass = (
                False if not is_class else issubclass(member[1], driver.BaseCamera)
            )
            not_gencam = member[1] is not driver.BaseCamera
            if is_class and is_subclass and not_gencam:
                self.drivers[member[1].name()] = member[1]

        self.ip = None
        self.port = None
        self.directory = os.path.expanduser("~/")
        self.file_name_format = "{timestamp}-{index}-{total}"
        self.config = None

        self.camera = None
        self.server = None

        self.is_live = False
        self.is_auto_exposure = False
        self.is_exposing = False
        self.run_live_task = False
        self.live_task = None
        self.run_auto_exposure_task = False
        self.auto_exposure_task = None
        self.log.debug("Generic Camera CSC Ready")

    async def begin_enable(self, id_data):
        """Begin do_enable; called before state changes.

        This method will start the liveview server and initialize the camera
        with the configuration sent during start.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        self.server = liveview.LiveViewServer(self.config.port, log=self.log)
        self.camera.initialise(config=self.config)

    async def begin_disable(self, id_data):
        """Begin do_disable; called before state changes.

        The method will check if the camera is exposing and reject the command
        in case an exposure is in course.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        if self.is_exposing:
            raise RuntimeError("Camera is exposing, cannot disable.")

    async def end_disable(self, id_data):
        """End do_disable; called after state changes but before command
        acknowledged.

        The method will stop any live view, close live view server and
        stop the camera.

        Parameters
        ----------
        id_data : `CommandIdData`
            Command ID and data
        """
        if self.is_live:
            try:
                self.run_live_task = False
                await self.live_task
                self.camera.stop_live_view()
            except Exception as e:
                self.log.error("Exception while stopping live task.")
                self.log.exception(e)

        if self.server is not None:
            try:
                await self.server.stop()
            except Exception as e:
                self.log.error("Exception while closing live view image server.")
                self.log.exception(e)
            finally:
                self.server = None

        if self.camera is not None:
            try:
                await self.camera.stop()
            except Exception as e:
                self.log.error("Exception while stopping camera.")
                self.log.exception(e)
            finally:
                self.camera = None
        self.log.info("end_disable")

    async def do_setValue(self, id_data):
        """Set a parameter/value pair.

        Parameters
        ----------
        id_data :
            id : `int`
                The command id.
            data : `GenericCamera_command_setValueC`
                parametersAndValues : `str`
                    A comma deliminated pair key,value.
        """
        self.assert_enabled("setValue")
        self._assert_notlive()

        self.log.info("setValue - Start")
        tokens = id_data.parametersAndValues.split(",")
        await self.camera.set_value(tokens[0], tokens[1])
        self.log.info("setValue - End")

    async def do_setROI(self, id_data):
        """Set the region of interest.

        Parameters
        ----------
        id_data :
            id : `int`
                The command id.
            data : `GenericCamera_command_setROIC`
                topPixel : `int`
                    The top pixel of the RIO in binned pixels.
                leftPixel : `int`
                    The left pixel of the RIO in binned pixels.
                width : `int`
                    The width of the ROI in binned pixels.
                height : `int`
                    The height of the ROI in binned pixels.
        """
        self.assert_enabled("setROI")
        self._assert_notlive()

        if self.evt_roi.set(
            topPixel=id_data.topPixel,
            leftPixel=id_data.leftPixel,
            width=id_data.width,
            height=id_data.height,
        ):
            self.log.debug("setROI - Start")
            self.camera.set_roi(
                id_data.topPixel, id_data.leftPixel, id_data.width, id_data.height
            )
            await self.evt_roi.write()
            self.log.debug("setROI - End")
        else:
            self.log.warning("ROI already set with same parameters.")

    async def do_setFullFrame(self, id_data):
        """Set the region of interest to full frame.

        Parameters
        ----------
        id_data :
            id : `int`
                The command id.
            data : `GenericCamera_command_setFullFrameC`
                ignored : bool
                    This is ignored.
        """
        self.log.info("setFullFrame - Start")
        self.assert_enabled("setFullFrame")
        self._assert_notlive()
        self.camera.set_full_frame()
        self.log.info("setFullFrame - End")

    async def do_startLiveView(self, id_data):
        """Starts the live view display.

        Parameters
        ----------
        id_data :
            id : int
                The command id.
            data : GenericCamera_command_startLiveViewC
                expTime : float
                    The exposure time for the live view."""
        self.assert_enabled("startLiveView")
        self.log.info("startLiveView - Start")
        self._assert_notlive()
        self._assert_notautoexposure()
        if id_data.expTime == 0.0:
            raise RuntimeError("LiveView exposure time must be greater than zero.")
        self.camera.start_live_view()
        self.run_live_task = True
        await asyncio.wait_for(self.server.start(), timeout=2)
        self.live_task = asyncio.ensure_future(self.liveView_loop(id_data.expTime))
        await self.evt_startLiveView.set_write(ip=self.ip, port=self.port)
        self.log.info("startLiveView - End")

    async def do_stopLiveView(self, id_data):
        """Stop the live view display.

        Parameters
        ----------
        id_data :
            id : `int`
                The command id.
            data : `GenericCamera_command_stopLiveViewC`
                ignored : `bool`
                    This is ignored.
        """
        self.assert_enabled("stopLiveView")
        self._assert_live()

        self.log.info("stopLiveView - Start")

        self.run_live_task = False
        await self.live_task

        await self.stop_liveview()

        self.log.info("stopLiveView - End")

    async def stop_liveview(self):
        """Stop live view."""

        try:
            await self.server.stop()
        except Exception as e:
            self.log.error("Exception trying to stop liveview.")
            self.log.exception(e)

        try:
            self.camera.stop_live_view()
        except Exception as e:
            self.log.error("Exception trying to stop liveview.")
            self.log.exception(e)

        await self.evt_endLiveView.write()

    async def do_takeImages(self, id_data):
        """Start taking images.

        Parameters
        ----------
        id_data :
            id : `int`
                The command id.
            data : `GenericCamera_command_takeImagesC`
                numImages : `int`
                    The number of images to take in the sequence.
                expTime : `float`
                    The exposure time in seconds.
                shutter : `bool`
                    True if the shutter should be utilized.
        """
        self.assert_enabled("takeImages")
        self._assert_notlive()
        self._assert_notautoexposure()
        self.is_exposing = True

        try:
            self.log.info("takeImages - Start")

            images_in_sequence = id_data.numImages
            exposure_time = id_data.expTime
            time_stamp = time.time()

            await self.evt_startTakeImage.write()
            await self.camera.start_take_image(
                exposure_time,
                id_data.shutter,
                id_data.sensors,
                id_data.keyValueMap,
                id_data.obsNote,
            )

            for image_index in range(images_in_sequence):
                timestamp = time.time()
                image_name = self.file_name_format.format(
                    timestamp=int(timestamp),
                    index=image_index,
                    total=images_in_sequence,
                )
                exposure = await self.take_image(
                    shutter=id_data.shutter,
                    images_in_sequence=images_in_sequence,
                    image_index=image_index,
                    exposure_time=exposure_time,
                    timestamp=time_stamp,
                    image_name=image_name,
                )
                exposure.save(os.path.join(self.directory, image_name + ".fits"))
            await self.camera.end_take_image()
            await self.evt_endTakeImage.write()
        except Exception as e:
            self.log.exception(e)
            raise e
        finally:
            self.is_exposing = False
        self.log.info("takeImages - End")

    async def take_image(
        self,
        shutter,
        images_in_sequence,
        image_index,
        exposure_time,
        timestamp,
        image_name,
    ):
        """Take a single image with the given parameters.

        Parameters
        ----------
        shutter: `bool`
            True if the shutter should be utilized.
        images_in_sequence: `int`
            The number of images to take in the sequence.
        image_index: `int`
            The index of the image in the sequence.
        exposure_time: `float`
            The exposure time in seconds.
        timestamp: `float`
            The time in seconds.
        image_name: `str`
            The name of the image file.
        Returns
        -------
        exposure: `exposure.Exposure`
            The exposure.
        """
        if shutter:
            await self.evt_startShutterOpen.write()
            await self.camera.start_shutter_open()

            await self.camera.end_shutter_open()
            await self.evt_endShutterOpen.write()

        await self.evt_startIntegration.set_write(
            imagesInSequence=images_in_sequence,
            imageName=image_name,
            imageIndex=image_index,
            timestampAcquisitionStart=timestamp,
            exposureTime=exposure_time,
        )
        await self.camera.start_integration()
        await self.camera.end_integration()
        await self.evt_endIntegration.write()

        if shutter:
            await self.evt_startShutterClose.write()
            await self.camera.start_shutter_close()

            await self.camera.end_shutter_close()
            await self.evt_endShutterClose.write()
        await self.evt_startReadout.set_write(
            imagesInSequence=images_in_sequence,
            imageName=image_name,
            imageIndex=image_index,
            timestampAcquisitionStart=timestamp,
            exposureTime=exposure_time,
        )
        await self.camera.start_readout()

        exposure = await self.camera.end_readout()
        await self.evt_endReadout.set_write(
            imagesInSequence=images_in_sequence,
            imageName=image_name,
            imageIndex=image_index,
            timestampAcquisitionStart=timestamp,
            requestedExposureTime=exposure_time,
        )
        return exposure

    async def do_startAutoExposure(self, id_data):
        """Start taking exposures automatically.

        Parameters
        ----------
        id_data :
            minExpTime : `float`
                The minimum exposure time in seconds.
            maxExpTime : `float`
                The maximum exposure time in seconds.
            configuration : `str`
                A Yaml string containing additional configuration
                parameters.
        """
        self.assert_enabled("startAutoExposure")
        self.log.info("startAutoExposure - Start")
        self._assert_notlive()
        self._assert_notautoexposure()
        self.run_auto_exposure_task = True

        # Prepare potential configuration items for the loop
        configuration = {
            "shutter": False,
            "sensors": "",
            "keyValueMap": "",
            "obsNote": "",
        }
        if id_data.configuration != "":
            loaded_configuration = yaml.safe_load(id_data.configuration)
            for key in configuration:
                if key in loaded_configuration:
                    configuration[key] = loaded_configuration[key]

        self.auto_exposure_task = asyncio.ensure_future(
            self.run_auto_exposure_loop(
                id_data.minExpTime, id_data.maxExpTime, configuration
            )
        )
        await self.evt_autoExposureStarted.set_write(
            minExpTime=id_data.minExpTime,
            maxExpTime=id_data.maxExpTime,
            configuration=id_data.configuration,
        )
        self.log.info("startAutoExposure - End")

    async def do_stopAutoExposure(self, id_data):
        """Stop taking exposures automatically.

        Parameters
        ----------
        id_data
            Nothing passed on.
        """
        self.assert_enabled("stopAutoExposure")
        self._assert_autoexposure()

        self.log.info("stopAutoExposure - Start")

        self.run_auto_exposure_task = False
        await self.auto_exposure_task

        await self.stop_autoexposure()

        self.log.info("stopAutoExposure - End")

    async def stop_autoexposure(self):
        """Stop auto exposure.

        Not much content for now but this may change in the future.
        """

        await self.evt_autoExposureStopped.write()

    async def liveView_loop(self, exposure_time):
        """Run the live view capture loop.

        Parameters
        ----------
        exposure_time : `float`
            The exposure time of the image (in seconds).
        """
        self.log.debug("liveView_loop - Start")
        self.is_live = True
        try:
            while self.run_live_task:
                await self.camera.start_take_image(
                    exposure_time, True, True, True, True
                )

                start_frame_time = time.time()

                self.log.debug("start shutter open")
                await self.camera.start_shutter_open()
                self.log.debug("end shutter open")
                await self.camera.end_shutter_open()
                self.log.debug("start integration")
                await self.camera.start_integration()
                self.log.debug("end integration")
                await self.camera.end_integration()
                self.log.debug("startShutterClose")
                await self.camera.start_shutter_close()
                self.log.debug("endShutterClose")
                await self.camera.end_shutter_close()
                self.log.debug("startReadout")
                await self.camera.start_readout()
                self.log.debug("endReadout")
                exposure = await self.camera.end_readout()
                self.log.debug("endTakeImage")
                await self.camera.end_take_image()
                exposure.make_jpeg()
                self.log.debug(f"{exposure.buffer}")
                await self.server.send_exposure(exposure)
                stop_frame_time = time.time()
                frame_time = round(stop_frame_time - start_frame_time, 3)
                self.log.debug(f"liveView_loop - {frame_time}")
        except Exception as e:
            self.log.error("Error in live view loop.")
            self.log.exception(e)
            await self.stop_liveview()

            await self.fault(
                code=LV_ERROR,
                report="Error in live view loop.",
                traceback=traceback.format_exc(),
            )

        self.is_live = False
        self.log.info("liveView_loop - End")

    async def run_auto_exposure_loop(self, min_exp_time, max_exp_time, configuration):
        """Prepare and start the auto exposure capture loop.

        The cadence of the images is determined by the value of
        config.auto_exposure_nterval.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing additional configuration parameters.
        """
        self.log.info("autoExposure_loop - Start")
        self.is_auto_exposure = True

        augmented_configuration = configuration.copy()
        augmented_configuration["images_in_sequence"] = 0
        augmented_configuration["image_index"] = 0
        augmented_configuration["exposure_time"] = min_exp_time

        try:
            await self.run_auto_exposure(
                min_exp_time, max_exp_time, augmented_configuration
            )
        except Exception:
            self.log.exception("Error in auto exposure loop.")
            await self.stop_autoexposure()

            await self.fault(
                code=AE_ERROR,
                report="Error in auto exposure loop.",
                traceback=traceback.format_exc(),
            )

        self.is_auto_exposure = False
        self.log.info("autoExposure_loop - End")

    async def run_auto_exposure(self, min_exp_time, max_exp_time, configuration):
        """Take auto exposures until `run_auto_exposure_task` is False.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing additional configuration parameters.
        """

        # First determine the exposure time based by taking images
        # starting from the configured minimum exposure time.
        timestamp = time.time()
        image_name = self.file_name_format.format(
            timestamp=int(timestamp), index=0, total=1
        )
        exposure_time_auto_current = await self.determine_exposure_time(
            min_exp_time, max_exp_time, configuration, timestamp, image_name
        )

        self.log.debug(
            f"Initial auto exposure time: {exposure_time_auto_current}s "
            f"[{min_exp_time}:{max_exp_time}]"
        )

        # Then loop and take images using the latest exposure time and
        # update the exposure time if necessary on the way.
        while self.run_auto_exposure_task:
            timestamp = time.time()
            image_name = self.file_name_format.format(
                timestamp=int(timestamp),
                index=configuration["image_index"],
                total=configuration["images_in_sequence"],
            )

            await self.evt_startTakeImage.write()
            await self.camera.start_take_image(
                exposure_time_auto_current,
                configuration["shutter"],
                configuration["sensors"],
                configuration["keyValueMap"],
                configuration["obsNote"],
            )

            # Create a sleep task to wait for while taking the image.
            task_timer = asyncio.create_task(
                asyncio.sleep(self.config.auto_exposure_interval)
            )
            # Take an exposure until the background level is within
            # the expected boundaries. This updates the exposure time
            # as well.
            (
                exposure,
                exposure_time_auto_new,
            ) = await self.get_auto_exposure_and_exposure_time(
                min_exp_time,
                max_exp_time,
                configuration,
                timestamp,
                image_name,
                exposure_time_auto_current,
            )

            if exposure:
                # Save the image.
                exposure.save(os.path.join(self.directory, image_name + ".fits"))
                # Update the initial exposure time for the next run of
                # the loop.
                self.log.debug(
                    f"Auto exposure time adjusted: {exposure_time_auto_current}s "
                    f"-> {exposure_time_auto_new}s."
                )
                exposure_time_auto_current = exposure_time_auto_new

            await self.camera.end_take_image()
            await self.evt_endTakeImage.write()

            # Now await the sleep task so either taking images is done
            # or a new one gets scheduled.
            await task_timer

    async def determine_exposure_time(
        self,
        min_exp_time,
        max_exp_time,
        configuration,
        timestamp,
        image_name,
    ):
        """Take images starting with the configured minimum exposure
        time and increasing it up to the maximum exposure time if
        necessary while determining the background level and verify
        it that is within the configured limits.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing configuration parameters.
        timestamp: `float`
            The timestamp of the exposure [s].
        image_name: `str`
            The name of the exposure file.

        Returns
        -------
        exposure_time: `float`
            The exposure time determined by inspecting the background
            level of images taken with varying exposure times.
        """
        exposure_time = configuration["exposure_time"]

        await self.camera.start_take_image(
            exposure_time,
            configuration["shutter"],
            configuration["sensors"],
            configuration["keyValueMap"],
            configuration["obsNote"],
        )

        background_level = 0.0
        while not (
            self.config.min_background <= background_level <= self.config.max_background
        ):
            self.log.debug("Taking exposure.")
            exposure = await self.take_image(
                configuration["shutter"],
                configuration["images_in_sequence"],
                configuration["image_index"],
                exposure_time,
                timestamp,
                image_name,
            )
            self.log.debug("Establishing exposure background level.")
            background_level = self.establish_exposure_background(exposure)
            self.log.debug(
                f"Background level is {background_level} and a value between "
                f"{self.config.min_background} and {self.config.max_background} "
                f"is expected."
            )
            new_exposure_time = await self.adjust_exposure_time(
                min_exp_time,
                max_exp_time,
                configuration,
                background_level,
                exposure_time,
            )

            if (
                not (
                    self.config.min_background
                    <= background_level
                    <= self.config.max_background
                )
                and new_exposure_time == exposure_time
            ):
                self.log.warn(
                    "Cannot take an exposure with a valid background level. Ignoring."
                )
                break

            exposure_time = new_exposure_time

        return exposure_time

    async def get_auto_exposure_and_exposure_time(
        self,
        min_exp_time,
        max_exp_time,
        configuration,
        timestamp,
        image_name,
        initial_exposure_time,
    ):
        """Take exposures and adjust the exposure time if necessary
        based on the background level of the image.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing additional configuration parameters.
        timestamp: `float`
            The timestamp of the exposure [s].
        image_name: `str`
            The name of the exposure file.
        initial_exposure_time: `float`
            The initial exposure time [s]

        Returns
        -------
        exposure: `exposure.Exposure`
            An exposure with a background level between the configured
            minimum and maximim exposure times.
        exposure_time: `float`
            The exposure time to use by the next run of the loop.
        """
        exposure = None
        exposure_time = initial_exposure_time

        self.log.debug("Taking exposure.")
        exposure = await self.take_image(
            configuration["shutter"],
            configuration["images_in_sequence"],
            configuration["image_index"],
            exposure_time,
            timestamp,
            image_name,
        )
        self.log.debug("Establishing exposure background level.")
        background_level = self.establish_exposure_background(exposure)
        self.log.debug(
            f"Background level is {background_level} and a value between "
            f"{self.config.min_background} and {self.config.max_background} "
            f"is expected."
        )
        new_exposure_time = await self.adjust_exposure_time(
            min_exp_time,
            max_exp_time,
            configuration,
            background_level,
            exposure_time,
        )

        exposure_time = new_exposure_time
        return exposure, exposure_time

    async def adjust_exposure_time(
        self, min_exp_time, max_exp_time, configuration, background_level, exposure_time
    ):
        """Adjust the exposure time based on the current exposure time
        and the background level.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `dict`
            A dict containing additional configuration parameters.
        background_level: `float`
            The background level to compare against the background
            level limits.
        exposure_time: `float`
            The current exposure time [s].

        Returns
        -------
        new_exposure_time: `float`
            The new exposure time based on the background level and
            the current exposure time.
        """
        new_exposure_time = exposure_time
        if background_level > self.config.max_background:
            new_exposure_time = exposure_time / 2.0
            if new_exposure_time < min_exp_time:
                new_exposure_time = min_exp_time
        elif background_level < self.config.min_background:
            new_exposure_time = exposure_time * 2.0
            if new_exposure_time > max_exp_time:
                new_exposure_time = max_exp_time
        return new_exposure_time

    def establish_exposure_background(self, exposure):
        background_level = np.median(exposure.buffer)
        return background_level

    @staticmethod
    def get_config_pkg():
        return "ts_config_ocs"

    async def configure(self, config):
        """Configure the CSC.

        Parameters
        ----------
        config : `object`
            The configuration as described by the schema at ``schema_path``,
            as a struct-like object.

        Notes
        -----
        Called when running the ``start`` command, just before changing
        summary state from `State.STANDBY` to `State.DISABLED`.
        """

        for instance in config.instances:
            if instance["sal_index"] == self.salinfo.index:
                break
        else:
            raise salobj.ExpectedError(
                f"No config found for sal_index={self.salinfo.index}"
            )

        settings = types.SimpleNamespace(**instance)
        self.config = settings
        self.ip = self.config.ip
        self.port = self.config.port

        if os.path.exists(os.path.expanduser(self.config.directory)):
            self.directory = os.path.expanduser(self.config.directory)
        else:
            raise RuntimeError(f"Directory {self.config.directory} does not exists.")

        self.file_name_format = self.config.file_name_format

        self.camera = self.drivers[self.config.camera](log=self.log)
        camera_config = self.config.config
        config_schema = self.camera.get_config_schema()
        validator = salobj.DefaultingValidator(config_schema)
        validator.validate(camera_config)

    def _assert_notlive(self):
        """Raise an exception if live view is active."""
        assert not self.is_live, "Live view is active."

    def _assert_live(self):
        """Raise an exception if live view is not active."""
        assert self.is_live, "Live view is not active."

    def _assert_notautoexposure(self):
        """Raise an exception if auto exposure is active."""
        assert not self.is_auto_exposure, "Auto exposure is active."

    def _assert_autoexposure(self):
        """Raise an exception if auto exposure is not active."""
        assert self.is_auto_exposure, "Auto exposure is not active."
