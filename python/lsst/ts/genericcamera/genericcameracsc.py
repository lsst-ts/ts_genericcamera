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
import time
import traceback
import inspect
import os
import logging
import yaml

import numpy as np

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
                False if not is_class else issubclass(member[1], driver.GenericCamera)
            )
            not_gencam = member[1] is not driver.GenericCamera
            if is_class and is_subclass and not_gencam:
                self.drivers[member[1].name()] = member[1]

        # Make sure all options in schema are valid
        for camera in self.config_validator.final_validator.schema["properties"][
            "camera"
        ]["enum"]:
            assert camera in self.drivers.keys(), (
                f"{camera} is not a valid option, " f"must one of {self.drivers.keys()}"
            )

        self.ip = None
        self.port = None
        self.directory = os.path.expanduser("~/")
        self.fileNameFormat = "{timestamp}-{index}-{total}"
        self.config = None

        self.camera = None
        self.server = None

        self.isLive = False
        self.isAutoExposure = False
        self.isExposing = False
        self.runLiveTask = False
        self.liveTask = None
        self.runAutoExposureTask = False
        self.autoExposureTask = None
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
        if self.isExposing:
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
        if self.isLive:
            try:
                self.runLiveTask = False
                await self.liveTask
                self.camera.stopLiveView()
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
                self.camera.stop()
            except Exception as e:
                self.log.error("Exception while stopping camera.")
                self.log.exception(e)
            finally:
                self.camera = None

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
        await self.camera.setValue(tokens[0], tokens[1])
        self.log.info("setValue - End")

    def do_setROI(self, id_data):
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
            self.camera.setROI(
                id_data.topPixel, id_data.leftPixel, id_data.width, id_data.height
            )
            self.evt_roi.put()
            self.log.debug("setROI - End")
        else:
            self.log.warning("ROI already set with same parameters.")

    def do_setFullFrame(self, id_data):
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
        self.camera.setFullFrame()
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
        self.camera.startLiveView()
        self.runLiveTask = True
        await asyncio.wait_for(self.server.start(), timeout=2)
        self.liveTask = asyncio.ensure_future(self.liveView_loop(id_data.expTime))
        self.evt_startLiveView.set_put(ip=self.ip, port=self.port)
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

        self.runLiveTask = False
        await self.liveTask

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
            self.camera.stopLiveView()
        except Exception as e:
            self.log.error("Exception trying to stop liveview.")
            self.log.exception(e)

        self.evt_endLiveView.put()

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
        self.isExposing = True

        try:
            self.log.info("takeImages - Start")

            imagesInSequence = id_data.numImages
            exposureTime = id_data.expTime
            timeStamp = time.time()

            self.evt_startTakeImage.put()
            await self.camera.startTakeImage(
                exposureTime,
                id_data.shutter,
                id_data.sensors,
                id_data.keyValueMap,
                id_data.obsNote,
            )

            for imageIndex in range(imagesInSequence):
                timestamp = time.time()
                imageName = self.fileNameFormat.format(
                    timestamp=int(timestamp),
                    index=imageIndex,
                    total=imagesInSequence,
                )
                exposure = await self.take_image(
                    shutter=id_data.shutter,
                    images_in_sequence=imagesInSequence,
                    image_index=imageIndex,
                    exposure_time=exposureTime,
                    timestamp=timeStamp,
                    image_name=imageName,
                )
                exposure.save(os.path.join(self.directory, imageName + ".fits"))
            await self.camera.endTakeImage()
            self.evt_endTakeImage.put()
        except Exception as e:
            self.log.exception(e)
            raise e
        finally:
            self.isExposing = False
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
            self.evt_startShutterOpen.put()
            await self.camera.startShutterOpen()

            await self.camera.endShutterOpen()
            self.evt_endShutterOpen.put()

        self.evt_startIntegration.set_put(
            imagesInSequence=images_in_sequence,
            imageName=image_name,
            imageIndex=image_index,
            timestampAcquisitionStart=timestamp,
            exposureTime=exposure_time,
        )
        await self.camera.startIntegration()
        await self.camera.endIntegration()
        self.evt_endIntegration.put()

        if shutter:
            self.evt_startShutterClose.put()
            await self.camera.startShutterClose()

            await self.camera.endShutterClose()
            self.evt_endShutterClose.put()
        self.evt_startReadout.set_put(
            imagesInSequence=images_in_sequence,
            imageName=image_name,
            imageIndex=image_index,
            timestampAcquisitionStart=timestamp,
            exposureTime=exposure_time,
        )
        await self.camera.startReadout()

        exposure = await self.camera.endReadout()
        self.evt_endReadout.set_put(
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
        self.runAutoExposureTask = True
        self.autoExposureTask = asyncio.ensure_future(
            self.run_auto_exposure_loop(
                id_data.minExpTime, id_data.maxExpTime, id_data.configuration
            )
        )
        self.evt_autoExposureStarted.set_put(
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

        self.runAutoExposureTask = False
        await self.autoExposureTask

        await self.stop_autoexposure()

        self.log.info("stopAutoExposure - End")

    async def stop_autoexposure(self):
        """Stop auto exposure.

        Not much content for now but this may change in the future.
        """

        self.evt_autoExposureStopped.put()

    async def liveView_loop(self, exposure_time):
        """Run the live view capture loop.

        Parameters
        ----------
        exposure_time : `float`
            The exposure time of the image (in seconds).
        """
        self.log.debug("liveView_loop - Start")
        self.isLive = True
        try:
            while self.runLiveTask:
                await self.camera.startTakeImage(exposure_time, True, True, True, True)

                startFrameTime = time.time()

                self.log.debug("start shutter open")
                await self.camera.startShutterOpen()
                self.log.debug("end shutter open")
                await self.camera.endShutterOpen()
                self.log.debug("start integration")
                await self.camera.startIntegration()
                self.log.debug("end integration")
                await self.camera.endIntegration()
                self.log.debug("startShutterClose")
                await self.camera.startShutterClose()
                self.log.debug("endShutterClose")
                await self.camera.endShutterClose()
                self.log.debug("startReadout")
                await self.camera.startReadout()
                self.log.debug("endReadout")
                exposure = await self.camera.endReadout()
                self.log.debug("endTakeImage")
                await self.camera.endTakeImage()
                exposure.makeJPEG()
                self.log.debug(f"{exposure.buffer}")
                await self.server.send_exposure(exposure)
                stopFrameTime = time.time()
                frameTime = round(stopFrameTime - startFrameTime, 3)
                self.log.debug(f"liveView_loop - {frameTime}")
        except Exception as e:
            self.log.error("Error in live view loop.")
            self.log.exception(e)
            await self.stop_liveview()

            self.fault(
                code=LV_ERROR,
                report="Error in live view loop.",
                traceback=traceback.format_exc(),
            )

        self.isLive = False
        self.log.info("liveView_loop - End")

    async def run_auto_exposure_loop(self, min_exp_time, max_exp_time, configuration):
        """Run the auto exposure capture loop.

        The cadence of the images is determined by the value of
        AUTO_EXP_IMAGE_INTERVAL.

        Parameters
        ----------
        min_exp_time: `float`
            The minimum exposure time to use.
        max_exp_time: `float`
            The maximum exposure time to use.
        configuration: `str`
            A Yaml string containing additional configuration
            parameters.
        """
        self.log.info("autoExposure_loop - Start")
        self.isAutoExposure = True

        shutter = False
        sensors = ""
        keyValueMap = ""
        obsNote = ""
        if configuration != "":
            config = yaml.safe_load(configuration)
            if "shutter" in config:
                shutter = config["shutter"]
            if "sensors" in config:
                sensors = config["sensors"]
            if "keyValueMap" in config:
                keyValueMap = config["keyValueMap"]
            if "obsNote" in config:
                obsNote = config["obsNote"]

        images_in_sequence = 0
        image_index = 0
        exposure_time = min_exp_time

        try:
            while self.runAutoExposureTask:
                timestamp = time.time()
                image_name = self.fileNameFormat.format(
                    timestamp=int(timestamp),
                    index=image_index,
                    total=images_in_sequence,
                )

                self.evt_startTakeImage.put()
                await self.camera.startTakeImage(
                    exposure_time,
                    shutter,
                    sensors,
                    keyValueMap,
                    obsNote,
                )
                exposure = None

                background_level = 0.0
                while not (
                    self.config.minBackground
                    <= background_level
                    <= self.config.maxBackground
                ):
                    self.log.debug("Taking exposure.")
                    exposure = await self.take_image(
                        shutter,
                        images_in_sequence,
                        image_index,
                        exposure_time,
                        timestamp,
                        image_name,
                    )
                    self.log.debug("Establishing exposure background level.")
                    background_level = await self.establish_exposure_background(
                        exposure
                    )
                    self.log.debug(
                        f"Background level is {background_level} and a value between "
                        f"{self.config.minBackground} and {self.config.maxBackground} "
                        f"is expected."
                    )
                    new_exposure_time = exposure_time
                    if background_level > self.config.maxBackground:
                        new_exposure_time = exposure_time / 2.0
                        if new_exposure_time < min_exp_time:
                            new_exposure_time = min_exp_time
                    elif background_level < self.config.minBackground:
                        new_exposure_time = exposure_time * 2.0
                        if new_exposure_time > max_exp_time:
                            new_exposure_time = max_exp_time

                    if (
                        not (
                            self.config.minBackground
                            <= background_level
                            <= self.config.maxBackground
                        )
                        and new_exposure_time == exposure_time
                    ):
                        self.log.warn(
                            "Cannot take an exposure with a valid background level. Ignoring."
                        )
                        exposure = None
                        break

                if exposure:
                    exposure.save(os.path.join(self.directory, image_name + ".fits"))

                await self.camera.endTakeImage()
                self.evt_endTakeImage.put()

                # Schedule the next image such that it starts
                # AUTO_EXP_IMAGE_INTERVAL seconds after the start of
                # the previous image cycle.
                now = time.time()
                time_diff = now - timestamp
                sleep_time = self.config.autoExposureInterval
                if time_diff < self.config.autoExposureInterval:
                    sleep_time = self.config.autoExposureInterval - time_diff
                await asyncio.sleep(sleep_time)

        except Exception as e:
            self.log.error("Error in auto exposure loop.")
            self.log.exception(e)
            await self.stop_autoexposure()

            self.fault(
                code=AE_ERROR,
                report="Error in auto exposure loop.",
                traceback=traceback.format_exc(),
            )

        self.isAutoExposure = False
        self.log.info("autoExposure_loop - End")

    async def establish_exposure_background(self, exposure):
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

        self.ip = config.ip
        self.port = config.port

        if os.path.exists(os.path.expanduser(config.directory)):
            self.directory = os.path.expanduser(config.directory)
        else:
            raise RuntimeError(f"Directory {config.directory} does not exists.")

        self.fileNameFormat = config.fileNameFormat

        self.camera = self.drivers[config.camera](log=self.log)
        self.config = config

    def _assert_notlive(self):
        """Raise an exception if live view is active."""
        if self.isLive:
            raise Exception()

    def _assert_live(self):
        """Raise an exception if live view is not active."""
        if not self.isLive:
            raise Exception()

    def _assert_notautoexposure(self):
        """Raise an exception if auto exposure is active."""
        if self.isAutoExposure:
            raise Exception()

    def _assert_autoexposure(self):
        """Raise an exception if auto exposure is not active."""
        if not self.isAutoExposure:
            raise Exception()
