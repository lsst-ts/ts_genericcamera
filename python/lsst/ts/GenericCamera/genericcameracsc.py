# This file is part of ts_GenericCamera.
#
# Developed for the LSST Telescope and Site Systems.
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
import pathlib
import time
import traceback
import inspect
import os
import logging

from lsst.ts import salobj

from .liveview import liveview
from . import driver


LV_ERROR = 1000
"""Error code for when the live view loop dies and the CSC is in enable
state.
"""


class GenericCameraCsc(salobj.ConfigurableCsc):

    valid_simulation_modes = (0, 1)

    def __init__(
        self,
        index,
        config_dir=None,
        initial_state=salobj.State.STANDBY,
        simulation_mode=0,
    ):

        schema_path = (
            pathlib.Path(__file__)
            .resolve()
            .parents[4]
            .joinpath("schema", "GenericCamera.yaml")
        )

        super().__init__(
            "GenericCamera",
            index=index,
            schema_path=schema_path,
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
        self.fileNameFormat = "{timestamp}-{name}-{index}-{total}"
        self.config = None

        self.camera = None
        self.server = None

        self.isLive = False
        self.isExposing = False
        self.runLiveTask = False
        self.liveTask = None
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
        """Sets a parameter/value pair.

        Parameters
        ----------
        id_data :
            id : int
                The command id.
            data : GenericCamera_command_setValueC
                parametersAndValues : str
                    A comma deliminated pair key,value.
        """
        self.assert_enabled("setValue")
        self._assert_notlive()

        self.log.info("setValue - Start")
        tokens = id_data.parametersAndValues.split(",")
        await self.camera.setValue(tokens[0], tokens[1])
        self.log.info("setValue - End")

    def do_setROI(self, id_data):
        """Sets the region of interest.

        Parameters
        ----------
        id_data :
            id : int
                The command id.
            data : GenericCamera_command_setROIC
                topPixel : int
                    The top pixel of the RIO in binned pixels.
                leftPixel : int
                    The left pixel of the RIO in binned pixels.
                width : int
                    The width of the ROI in binned pixels.
                height : int
                    The height of the ROI in binned pixels."""
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
        """Sets the region of interest to full frame.

        Parameters
        ----------
        id_data :
            id : int
                The command id.
            data : GenericCamera_command_setFullFrameC
                ignored : bool
                    This is ignored."""
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
        if id_data.expTime == 0.0:
            raise RuntimeError("LiveView exposure time must be greater than zero.")
        self.camera.startLiveView()
        self.runLiveTask = True
        await asyncio.wait_for(self.server.start(), timeout=2)
        self.liveTask = asyncio.ensure_future(self.liveView_loop(id_data.expTime))
        self.evt_startLiveView.set_put(ip=self.ip, port=self.port)
        self.log.info("startLiveView - End")

    async def do_stopLiveView(self, id_data):
        """Stops the live view display.

        Parameters
        ----------
        id_data :
            id : int
                The command id.
            data : GenericCamera_command_stopLiveViewC
                ignored : bool
                    This is ignored."""
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
        """Starts taking images.

        Parameters
        ----------
        id_data :
            id : int
                The command id.
            data : GenericCamera_command_takeImagesC
                numImages : int
                    The number of images to take in the sequence.
                expTime : float
                    The exposure time in seconds.
                shutter : bool
                    True if the shutter should be utilized.
                imageSequenceName : str
                    The name of the image sequence."""
        self.assert_enabled("takeImages")
        self._assert_notlive()
        self.isExposing = True

        try:
            self.log.info("takeImages - Start")

            imageSequenceName = id_data.imageSequenceName
            imagesInSequence = id_data.numImages
            exposureTime = id_data.expTime
            timeStamp = time.time()

            self.evt_startTakeImage.put()
            await self.camera.startTakeImage(
                exposureTime,
                id_data.shutter,
                id_data.science,
                id_data.guide,
                id_data.wfs,
            )

            for imageIndex in range(imagesInSequence):
                timestamp = time.time()
                imageName = self.fileNameFormat.format(
                    timestamp=int(timestamp),
                    name=imageSequenceName,
                    index=imageIndex,
                    total=imagesInSequence,
                )
                if id_data.shutter:
                    self.evt_startShutterOpen.put()
                    await self.camera.startShutterOpen()

                    await self.camera.endShutterOpen()
                    self.evt_endShutterOpen.put()

                self.evt_startIntegration.set_put(
                    imageSequenceName=imageSequenceName,
                    imagesInSequence=imagesInSequence,
                    imageName=imageName,
                    imageIndex=imageIndex,
                    timeStamp=timeStamp,
                    exposureTime=exposureTime,
                )
                await self.camera.startIntegration()
                await self.camera.endIntegration()
                self.evt_endIntegration.put()

                if id_data.shutter:
                    self.evt_startShutterClose.put()
                    await self.camera.startShutterClose()

                    await self.camera.endShutterClose()
                    self.evt_endShutterClose.put()
                self.evt_startReadout.set_put(
                    imageSequenceName=imageSequenceName,
                    imagesInSequence=imagesInSequence,
                    imageName=imageName,
                    imageIndex=imageIndex,
                    timeStamp=timeStamp,
                    exposureTime=exposureTime,
                )
                await self.camera.startReadout()

                exposure = await self.camera.endReadout()
                self.evt_endReadout.set_put(
                    imageSequenceName=imageSequenceName,
                    imagesInSequence=imagesInSequence,
                    imageName=imageName,
                    imageIndex=imageIndex,
                    timeStamp=timeStamp,
                    exposureTime=exposureTime,
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

    async def liveView_loop(self, exposureTime):
        """Run the live view capture loop.

        Parameters
        ----------
        exposureTime : float
            The exposure time of the image (in seconds).
        """
        self.log.debug("liveView_loop - Start")
        self.isLive = True
        try:
            while self.runLiveTask:
                await self.camera.startTakeImage(exposureTime, True, True, True, True)

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

    @staticmethod
    def get_config_pkg():
        return "ts_config_ocs"

    async def configure(self, config):
        """Implement method to configure the CSC.

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
        """Raise an exception if live view is active.
        """
        if self.isLive:
            raise Exception()

    def _assert_live(self):
        """Raise an exception if live view is not active.
        """
        if not self.isLive:
            raise Exception()
