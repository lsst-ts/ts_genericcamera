# This file is part of ts_GenericCamera.
#
# Developed for the LSST.
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
import datetime
import logging
import time
import traceback
import os

from lsst.ts import salobj
import SALPY_GenericCamera
import liveview
import zwocamera
import simulatorcamera


class GenericCameraCsc(salobj.BaseCsc):
    def __init__(self, publishIP, initial_state=salobj.State.STANDBY, initial_simulation_mode=0):
        super().__init__(SALPY_GenericCamera, index=0, initial_state=initial_state,
                         initial_simulation_mode=initial_simulation_mode)
        self.salinfo.manager.setDebugLevel(0)
        self.ip = publishIP
        self.port = 5013
        # self.camera = zwocamera.ASICamera()
        self.camera = simulatorcamera.SimulatorCamera()
        self.camera.initialise("")
        self.server = None
        self.directory = "/home/ccontaxis/"
        self.fileNameFormat = "{timestamp}-{name}-{index}-{total}"
        self.server = liveview.LiveViewServer(self.port)
        self.isLive = False
        self.runLiveTask = False
        self.liveTask = None
        self._info("Generic Camera CSC Ready")

    def __del__(self):
        if self.server is not None:
            self.server.close()
            self.server = None

    async def do_setValue(self, id_data):
        """Sets a parameter/value pair.

        Parameters
        ----------
        id_data :
            id : int
                The command id.
            data : GenericCamera_command_setValueC
                parametersAndValues : str
                    A comma deliminated pair key,value."""
        self._info("setValue - Start")
        tokens = id_data.data.parametersAndValues.split(",")
        await self.camera.setValue(tokens[0], tokens[1])
        self._info("setValue - End")

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
        self._info("setROI - Start")
        self._assertNotLive()
        self.camera.setROI(id_data.data.topPixel,
                           id_data.data.leftPixel,
                           id_data.data.width,
                           id_data.data.height)
        self._logevent_roi(id_data.data.topPixel,
                           id_data.data.leftPixel,
                           id_data.data.width,
                           id_data.data.height)
        self._info("setROI - End")

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
        self._info("setFullFrame - Start")
        self._assertNotLive()
        self.camera.setFullFrame()
        self._info("setFullFrame - End")

    def do_startLiveView(self, id_data):
        """Starts the live view display.

        Parameters
        ----------
        id_data :
            id : int
                The command id.
            data : GenericCamera_command_startLiveViewC
                expTime : float
                    The exposure time for the live view."""
        self._info("startLiveView - Start")
        self._assertNotLive()
        self.camera.startLiveView()
        self.runLiveTask = True
        self.liveTask = asyncio.ensure_future(self.liveView_loop(id_data.data.expTime))
        self._logevent_startLiveView(self.ip, self.port)
        self._info("startLiveView - End")

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
        self._info("stopLiveView - Start")
        self._assertLive()
        self.runLiveTask = False
        await self.liveTask
        self.camera.stopLiveView()
        self._logevent_endLiveView()
        self._info("stopLiveView - End")

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
        self._info("takeImages - Start")
        self._assertNotLive()
        imageSequenceName = id_data.data.imageSequenceName
        imagesInSequence = id_data.data.numImages
        exposureTime = id_data.data.expTime
        timeStamp = time.time()
        await self.camera.startTakeImage(exposureTime)
        self._logevent_startTakeImage()
        for imageIndex in range(imagesInSequence):
            timestamp = time.time()
            imageName = self.fileNameFormat.format(timestamp = int(timestamp), name = imageSequenceName, index = imageIndex, total = imagesInSequence)
            if id_data.data.shutter:
                await self.camera.startShutterOpen()
                self._logevent_startShutterOpen()
                await self.camera.endShutterOpen()
                self._logevent_endShutterOpen()
            await self.camera.startIntegration()
            self._logevent_startIntegration(imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime)
            await self.camera.endIntegration()
            self._logevent_endIntegration()
            if id_data.data.shutter:
                await self.camera.startShutterClose()
                self._logevent_startShutterClose()
                await self.camera.endShutterClose()
                self._logevent_endShutterClose()
            await self.camera.startReadout()
            self._logevent_startReadout(imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime)
            exposure = await self.camera.endReadout()
            self._logevent_endReadout(imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime)
            exposure.save(os.path.join(self.directory, imageName + ".fits"))
        await self.camera.endTakeImage()
        self._logevent_endTakeImage()
        self._info("takeImages - End")

    async def liveView_loop(self, exposureTime):
        """Run the live view capture loop.

        Parameters
        ----------
        exposureTime : float
            The exposure time of the image."""
        self._info("liveView_loop - Start")
        self.isLive = True
        try:
            await self.camera.startTakeImage(exposureTime)
            while self.runLiveTask:
                startFrameTime = time.time()
                self.server.checkForClients()
                await self.camera.startShutterOpen()
                await self.camera.endShutterOpen()
                await self.camera.startIntegration()
                await self.camera.endIntegration()
                await self.camera.startShutterClose()
                await self.camera.endShutterClose()
                await self.camera.startReadout()
                exposure = await self.camera.endReadout()
                exposure.makeJPEG()
                self.server.sendExposure(exposure)
                stopFrameTime = time.time()
                frameTime = round(stopFrameTime - startFrameTime, 3)
                self._debug(f"liveView_loop - {frameTime}")
            await self.camera.endTakeImage()
        except Exception as e:
            traceback.print_exc()
        self.isLive = False
        self._info("liveView_loop - End")

    def _logevent_roi(self, top, left, width, height):
        """Publish the roi event.
        
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
        data = self.evt_roi.DataType()
        data.topPixel = top
        data.leftPixel = left
        data.width = width
        data.height = height
        self.evt_roi.put(data)

    def _logevent_startLiveView(self, ip, port):
        """Publish the startLiveView event.

        Parameters
        ----------
        ip : str
            The IP address of the live view server.
        port : int
            The port of the live view server."""
        data = self.evt_startLiveView.DataType()
        data.ip = ip
        data.port = port
        self.evt_startLiveView.put(data)

    def _logevent_endLiveView(self):
        """Publish the endLiveView event.
        """
        data = self.evt_endLiveView.DataType()
        self.evt_endLiveView.put(data)

    def _logevent_startTakeImage(self):
        """Publish the startTakeImage event.
        """
        data = self.evt_startTakeImage.DataType()
        self.evt_startTakeImage.put(data)

    def _logevent_startShutterOpen(self):
        """Publish the startShutterOpen event.
        """
        data = self.evt_startShutterOpen.DataType()
        self.evt_startShutterOpen.put(data)

    def _logevent_endShutterOpen(self):
        """Publish the endShutterOpen event.
        """
        data = self.evt_endShutterOpen.DataType()
        self.evt_endShutterOpen.put(data)

    def _logevent_startIntegration(self, imageSequenceName, imagesInSequence, imageName, imageIndex,
                                   timeStamp, exposureTime):
        """Publish the startIntegration event.

        Parameters
        ----------
        imageSequenceName : str
            The name of the image sequence.
        imagesInSequence : int
            The number of images in this sequence.
        imageName : int
            The name of the image being integrated.
        imageIndex : int
            The index of the image (0 based).
        timeStamp : float
            The time stamp of the image.
        exposureTime : float
            The exposure time of the image."""
        data = self.evt_startIntegration.DataType()
        data.imageSequenceName = imageSequenceName
        data.imagesInSequence = imagesInSequence
        data.imageName = imageName
        data.imageIndex = imageIndex
        data.timeStamp = timeStamp
        data.exposureTime = exposureTime
        self.evt_startIntegration.put(data)

    def _logevent_endIntegration(self):
        """Publish the endIntegration event.
        """
        data = self.evt_endIntegration.DataType()
        self.evt_endIntegration.put(data)

    def _logevent_startShutterClose(self):
        """Publish the startShutterClose event.
        """
        data = self.evt_startShutterClose.DataType()
        self.evt_startShutterClose.put(data)

    def _logevent_endShutterClose(self):
        """Publish the endShutterClose event.
        """
        data = self.evt_endShutterClose.DataType()
        self.evt_endShutterClose.put(data)

    def _logevent_startReadout(self, imageSequenceName, imagesInSequence, imageName, imageIndex,
                               timeStamp, exposureTime):
        """Publish the startReadout event.

        Parameters
        ----------
        imageSequenceName : str
            The name of the image sequence.
        imagesInSequence : int
            The number of images in this sequence.
        imageName : int
            The name of the image being integrated.
        imageIndex : int
            The index of the image (0 based).
        timeStamp : float
            The time stamp of the image.
        exposureTime : float
            The exposure time of the image."""
        data = self.evt_startReadout.DataType()
        data.imageSequenceName = imageSequenceName
        data.imagesInSequence = imagesInSequence
        data.imageName = imageName
        data.imageIndex = imageIndex
        data.timeStamp = timeStamp
        data.exposureTime = exposureTime
        self.evt_startReadout.put(data)

    def _logevent_endReadout(self, imageSequenceName, imagesInSequence, imageName, imageIndex,
                             timeStamp, exposureTime):
        """Publish the endReadout event.

        Parameters
        ----------
        imageSequenceName : str
            The name of the image sequence.
        imagesInSequence : int
            The number of images in this sequence.
        imageName : int
            The name of the image being integrated.
        imageIndex : int
            The index of the image (0 based).
        timeStamp : float
            The time stamp of the image.
        exposureTime : float
            The exposure time of the image."""
        data = self.evt_endReadout.DataType()
        data.imageSequenceName = imageSequenceName
        data.imagesInSequence = imagesInSequence
        data.imageName = imageName
        data.imageIndex = imageIndex
        data.timeStamp = timeStamp
        data.exposureTime = exposureTime
        self.evt_endReadout.put(data)

    def _logevent_endTakeImage(self):
        """Publish the endTakeImage event.
        """
        data = self.evt_endTakeImage.DataType()
        self.evt_endTakeImage.put(data)

    def _debug(self, message):
        """Write a debug message.

        Parameters
        ----------
        message : str
            The message."""
        self._logMessage(logging.DEBUG, message)

    def _info(self, message):
        """Write an info message.

        Parameters
        ----------
        message : str
            The message."""
        self._logMessage(logging.INFO, message)

    def _warn(self, message):
        """Write a warning message.

        Parameters
        ----------
        message : str
            The message."""
        self._logMessage(logging.WARNING, message)

    def _error(self, message):
        """Write an error message.

        Parameters
        ----------
        message : str
            The message."""
        self._logMessage(logging.ERROR, message)
    
    def _critical(self, message):
        """Write a critical message.

        Parameters
        ----------
        message : str
            The message."""
        self._logMessage(logging.CRITICAL, message)

    def _logMessage(self, level, message):
        """Write a log message.

        Parameters
        ----------
        level : logging.LEVEL
            The logging level.
        message : str
            The message."""
        date = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
        print(f"{date}\t{level} - {message}")
        if level == logging.DEBUG:
            self.log.debug(message)
        elif level == logging.INFO:
            self.log.info(message)
        elif level == logging.WARNING:
            self.log.warn(message)
        elif level == logging.ERROR:
            self.log.error(message)
        elif level == logging.CRITICAL:
            self.log.critical(message)

    def _assertNotLive(self):
        """Raise an exception if live view is active.
        """
        if self.isLive:
            raise Exception()

    def _assertLive(self):
        """Raise an exception if live view is not active.
        """
        if not self.isLive:
            raise Exception()

if __name__ == '__main__':
    csc = GenericCameraCsc("127.0.0.1", initial_state=salobj.State.ENABLED)
    asyncio.get_event_loop().run_until_complete(csc.done_task)