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

import astropy.io
import asyncio
import ctypes
import io
import numpy as np
from PIL import Image
import socket
import struct


class Exposure():
    """This class is used to define an exposure. It provides methods
    for manipulating an exposure and saving it to the local disk.
    """
    def __init__(self, buffer, width, height, tags, isJPEG=False):
        """Constructs an exposure object.

        Exposures meant to be a JPEG image should have 8bit pixels.
        Exposures meant to be a FITS image should have 16bit pixels.

        Parameters
        ----------
        buffer : buffer
            The buffer containing the image data.
        width : int
            The width of the image.
        height : int
            The height of the image.
        tags : map
            A list of tags that describe the image.
        isJPEG : bool (optional)
            True if the image described is a JPEG."""
        self.buffer = buffer
        self.width = width
        self.height = height
        self.tags = tags
        self.isJPEG = isJPEG

    def makeJPEG(self):
        """Takes this exposure and converts it to a JPEG.
        """
        fileMemory = io.BytesIO()
        img = Image.frombuffer('L', (self.width, self.height), self.buffer)
        img.save(fileMemory, 'jpeg')
        self.buffer = np.asarray(fileMemory.getbuffer())
        self.isJPEG = True

    def save(self, filePath):
        """Saves this exposure to the local drive.
        
        Parameters
        ----------
        filePath : str
            The path to the file to save the image to."""
        if self.isJPEG:
            img = Image.open(io.BytesIO(self.buffer))
            img.save(filePath, 'jpeg')
        else:
            try:
                count = int(self.width * self.height)
                ints = struct.unpack('H'*count, self.buffer)
                pixels = np.asarray(ints)
                imgPix = np.reshape(pixels, (self.height, self.width))
                imgPix = imgPix.astype(np.uint16)
                img = astropy.io.fits.PrimaryHDU(imgPix)
                hdul = astropy.io.fits.HDUList([img])
                hdr = hdul[0].header
                # for key in self.tags:
                #     hdr[key] = self.tags[key]
                hdul.writeto(filePath)
            except e:
                print(f"Failed to save image to file {filePath}.")


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

    def setValue(self, key, value):
        """Set a unique property of the camera.

        Parameters
        ----------
        key : str
            The name of the property.
        value : str
            The value of the property."""
        pass

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

    def setFullFrame(self):
        """Sets the region of interest to the whole sensor.
        """
        pass

    def setExposureTime(self, duration):
        """Sets the exposure time.

        Parameters
        ----------
        duration : float
            The exposure time in seconds."""
        pass

    def configureForLiveView(self):
        """Configure the camera for live view.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""
        pass

    def configureForExposure(self):
        """Configure the camera for a standard exposure.
        """
        pass

    async def takeExposure(self):
        """Take an exposure with the currently configured settings.

        The exposure should be the raw image data from the camera which
        most likely means a buffer created by ctypes.create_string_buffer()

        The Exposure class handles converting the image to the correct
        format. If live view, the image data is converted into a JPEG
        to be sent over a TCP socket. If a standard exposure then the
        image data is converted into a FITS to be saved onto the local
        machine.

        Returns
        -------
        Exposure
            The exposure captured by the camera."""
        return Exposure(ctypes.create_string_buffer(size=1),1,1, {})


class LiveViewServer():
    """This class defines a live view server. A live view server is a 
    TCP server that sends JPEG image data to clients to display in a 
    live GUI display.

    The TCP message format is as follows
    [SYNC][WIDTH][HEIGHT][ISJPEG][LENGTH][BUFFER]
    SYNC = 0xCAFEF00D (big endian)
    WIDTH = Width of image as 4 bytes (big endian)
    HEIGHT = Height of image as 4 bytes (big endian)
    ISJPEG = 1 if the buffer is a JPEG, 1 byte
    LENGTH = Length of the buffer as 4 bytes (big endian)
    BUFFER = The image data with the length specified
             in the LENGTH field.
    """
    def __init__(self, port):
        """Constructs a live view server that sends JPEG images
        to clients when instructed to.

        Parameters
        ----------
        port : int
            The port to listen to."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('0.0.0.0', port))
        self.sock.settimeout(0.1)
        self.sock.listen(5)
        self.clients = []
        self.isConnected = True

    def close(self):
        """Closes the live view server.
        """
        if self.isConnected:
            for client in self.clients:
                client.close()
            self.sock.close()
            self.clients = []
            self.isConnected = False

    def checkForClients(self):
        """Checks the socket for new clients attempting to connect
        to the socket.
        """
        self._assertConnected()
        try:
            conn, addr = self.sock.accept()
            self.clients.append(conn)
        except socket.timeout:
            pass

    def sendExposure(self, exposure):
        """Sends an exposure to all connected clients.

        If there is a problem while sending data to a client then
        that client is automatically removed.

        Parameters
        ----------
        exposure : Exposure
            The exposure to send to the clients."""
        self._assertConnected()
        newClients = []
        for i in range(len(self.clients)):
            client = self.clients[i]
            try:
                client.send((0xCAFEF00D).to_bytes(4, byteorder='big'))
                client.send((exposure.width).to_bytes(4, byteorder='big'))
                client.send((exposure.height).to_bytes(4, byteorder='big'))
                client.send(int(exposure.isJPEG).to_bytes(4, byteorder='big'))
                client.send((len(exposure.buffer)).to_bytes(4, byteorder='big'))
                client.send(exposure.buffer)
                newClients.append(client)
            except BrokenPipeError:
                pass
            except ConnectionResetError:
                pass

    def _assertConnected(self):
        if not self.isConnected:
            raise ConnectionError()


class LiveViewClient():
    """This class defines a live view client. It connects to
    a live view server to receive live JPEG images from a 
    camera.
    """
    def __init__(self, ip, port):
        """Constructs a live view client to receive data from
        a live view server.

        Parameters
        ----------
        ip : str
            The ip of the LiveViewServer to connect to.
        port : int
            The port of the LiveViewServer to connect to."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip, port))
        self.sock.settimeout(0.5)
        self.isConnected = True

    def close(self):
        """Closes this connection to the LiveViewServer.
        """
        if self.isConnected:
            self.sock.close()
            self.isConnected = False

    def receiveExposure(self):
        """Attempts to receive an exposure from the LiveViewServer.

        If a connection problem occurs then a ConnectionError is raised.
        If no image is available then an ImageReceiveError is raised.

        If for some reason the received image is corrupt then this
        method will attempt to re-sync to the sync code.

        Returns
        -------
        Exposure
            The exposure received from the LiveViewServer."""
        self._assertConnected()
        try:
            sync = int.from_bytes(self.sock.recv(4), byteorder='big')
            while True:
                if sync == 0xCAFEF00D:
                    width = int.from_bytes(self.sock.recv(4), byteorder='big')
                    height = int.from_bytes(self.sock.recv(4), byteorder='big')
                    isJPEG = bool(int.from_bytes(self.sock.recv(4), byteorder='big'))
                    length = int.from_bytes(self.sock.recv(4), byteorder='big')
                    if length > 0:
                        imgBuffer = b''
                        while len(imgBuffer) < length:
                            packet = self.sock.recv(length - len(imgBuffer))
                            if not packet:
                                break
                            imgBuffer += packet
                        if len(imgBuffer) == length:
                            return Exposure(imgBuffer, width, height, {}, isJPEG)
                else:
                    value = int.from_bytes(self.sock.recv(1), byteorder='big')
                    sync = ((sync & 0x00FFFFFF) << 8) | value
        except socket.timeout:
            pass
        except BrokenPipeError:
            self.isConnected = False
            raise ConnectionError()
        except ConnectionResetError:
            self.isConnected = False
            raise ConnectionError()
        raise ImageReceiveError()

    def _assertConnected(self):
        if not self.isConnected:
            raise ConnectionError()


class ImageReceiveError(Exception):
    def __init__(self):
        super().__init__()
