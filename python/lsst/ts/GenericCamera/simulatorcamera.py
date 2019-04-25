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

import asyncio
import numpy as np

import exposure
import genericcamera


class SimulatorCamera(genericcamera.GenericCamera):
    def __init__(self):
        self.isLiveExposure = False
        self.maxWidth = 1024
        self.maxHeight = 1024
        self.topPixel = 0
        self.leftPixel = 0
        self.width = self.maxWidth
        self.height = self.maxHeight
        self.bytesPerPixel = 2
        self.exposureTime = 0.001
        self.imageBuffer = None

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : str
            The name of the configuration file to load."""
        pass

    def getMakeAndModel(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        info = self.dev.getCameraInfo()
        return "Simulator"

    def getValue(self, key):
        """Gets the value of a unique property of the camera.
        Parameters
        ----------
        key : str
            The name of the property.
        Returns
        -------
        str
            The value of the property.
            Returns 'UNDEFINED' if the property doesn't exist. """
        return super().getValue(key)

    async def setValue(self, key, value):
        """Set a unique property of the camera.

        Parameters
        ----------
        key : str
            The name of the property.
        value : str
            The value of the property."""
        key = key.lower()
        await super().setValue(key, value)

    def getROI(self):
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
        return self.topPixel, self.leftPixel, self.width, self.height

    def setROI(self, top, left, width, height):
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
        self.topPixel = top
        self.leftPixel = left
        self.width = width
        self.height = height

    def setFullFrame(self):
        """Sets the region of interest to the whole sensor.
        """
        self.setROI(0, 0, self.maxWidth, self.maxHeight)

    def startLiveView(self):
        """Configure the camera for live view.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""
        self.bytesPerPixel = 1
        self.isLiveExposure = True
        super().startLiveView()

    def stopLiveView(self):
        """Configure the camera for a standard exposure.
        """
        self.bytesPerPixel = 2
        self.isLiveExposure = False
        super().stopLiveView()

    async def startTakeImage(self, expTime):
        """Start take image.

        Parameters
        ----------
        expTime : float
            The exposure time in seconds."""
        self.exposureTime = expTime
        imageByteCount = self.width * self.height * self.bytesPerPixel
        buffer = np.zeros(imageByteCount, dtype=np.uint8)
        index = 0
        for y in range(self.height):
            yPixel = y + self.topPixel
            for x in range(self.width):
                xPixel = x + self.leftPixel
                pixelValue = yPixel + int(xPixel * self.exposureTime)
                if self.bytesPerPixel == 1:
                    buffer[index + 0] = pixelValue & 0xFF
                elif self.bytesPerPixel == 2:
                    buffer[index + 0] = pixelValue & 0xFF
                    buffer[index + 1] = (pixelValue << 8) & 0xFF
                index = index + self.bytesPerPixel
        self.imageBuffer = buffer
        await super().startTakeImage(expTime)

    async def endIntegration(self):
        """End integration.

        This should wait for the integration period to complete."""
        await asyncio.sleep(self.exposureTime)
        await super().endIntegration()

    async def endReadout(self):
        """Start reading out the image.
        """
        image = await super().startReadout()
        image = exposure.Exposure(self.imageBuffer, self.width, self.height, {})
        return image
