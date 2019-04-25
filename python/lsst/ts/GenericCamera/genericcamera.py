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
import ctypes

import exposure


class GenericCamera():
    """This class describes the methods required by a generic camera.
    """
    def __init__(self):
        pass

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
        return "GenericCamera"

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
        return "UNDEFINED"

    async def setValue(self, key, value):
        """Set a unique property of the camera.

        Parameters
        ----------
        key : str
            The name of the property.
        value : str
            The value of the property."""
        pass

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
        return 0, 0, 0, 0

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
        pass

    def setFullFrame(self):
        """Sets the region of interest to the whole sensor.
        """
        pass

    def startLiveView(self):
        """Starts a live view data stream from the camera.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""
        pass

    def stopLiveView(self):
        """Stops an active live view data stream from the camera.

        This should review the image format back to 16bits per pixel."""
        pass

    async def startTakeImage(self, expTime):
        """Start taking an image or a set of images.

        Parameters
        ----------
        expTime : float
            The exposure time in seconds."""
        return True

    async def startShutterOpen(self):
        """Start opening the shutter.

        If the camera doesn't have a shutter then don't do anything."""
        pass

    async def endShutterOpen(self):
        """End opening the shutter.

        If the camera does have a shutter then this should wait for the
        shutter to finish opening.

        If the camera doesn't have a shutter then don't do anything."""
        pass

    async def startIntegration(self):
        """Start integrating.
        """
        pass

    async def endIntegration(self):
        """End integration.

        This should wait for the integration period to complete."""
        pass

    async def startShutterClose(self):
        """Start closing the shutter.

        If the camera does have a shutter then start closing the
        shutter.

        If the camera doesn't have a shutter then don't do anything."""
        pass

    async def endShutterClose(self):
        """End closing the shutter.

        If the camera does have a shutter then this should wait for
        the shutter to finishing closing.

        If the camera doesn't have a shutter then don't do anything."""
        pass

    async def startReadout(self):
        """Start reading out the image.
        """
        pass

    async def endReadout(self):
        """End reading out the image.

        Returns
        -------
        exposure.Exposure
            The exposure."""
        return exposure.Exposure(ctypes.create_string_buffer(size=1),1,1, {})

    async def endTakeImage(self):
        """End take image or images.
        """
        pass
