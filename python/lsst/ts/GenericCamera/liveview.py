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

import socket

import exposure


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
        self.sock.settimeout(0.02)
        self.sock.listen(5)
        self.clients = []
        self.isConnected = True

    def close(self):
        """Closes the live view server.
        """
        if self.isConnected:
            for client in self.clients:
                # client.shutdown(socket.SHUT_RDWR)
                client.close()
            self.sock.shutdown(socket.SHUT_RDWR)
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
        self.sock.settimeout(0.02)
        self.isConnected = True

    def close(self):
        """Closes this connection to the LiveViewServer.
        """
        if self.isConnected:
            # self.sock.shutdown(socket.SHUT_RD)
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
                            return exposure.Exposure(imgBuffer, width, height, {}, isJPEG)
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
