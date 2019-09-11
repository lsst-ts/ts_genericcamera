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

__all__ = ['LiveViewServer', 'LiveViewClient', 'AsyncLiveViewClient']

import asyncio
import socket
import logging

import numpy as np

from lsst.ts.GenericCamera import exposure


class LiveViewServer:
    """This class defines a live view server. A live view server is a
    TCP server that sends JPEG image data to clients to display in a
    live GUI display.

    The TCP message format is as follows
    [START]\r\n
    WIDTH\r\n
    HEIGHT\r\n
    ISJPEG\r\n
    LENGTH\r\n
    BUFFER\r\n

    Parameters
    ----------
    port : int
        TCP/IP port.
    """

    def __init__(self, port, host="0.0.0.0", log=None):

        # Host must be a valid IP that can be used to create a server.
        self.host = host
        self.port = port

        self._server = None
        self.log = log if log is not None else logging.getLogger(__name__)

        self._exposure = None

        self.bcast_lock = asyncio.Lock()
        self.broad_cast = False
        self.new_exposure_available = asyncio.Event()

    async def start(self):
        """Start the TCP/IP server.
        Set start_task done and start the command loop.
        """
        self.log.info("Starting TCP/IP server...")
        self.broad_cast = True

        self._server = await asyncio.start_server(self.broadcast_loop,
                                                  host=self.host,
                                                  port=self.port)

    async def stop(self):
        """Stop the TCP/IP server.
        """
        if self._server is None:
            return

        self.broad_cast = False
        server = self._server
        self._server = None
        server.close()
        await asyncio.wait_for(server.wait_closed(), timeout=5)

    async def broadcast_loop(self, reader, writer):
        """Wait for new image to be available and broadcast it."""

        self.log.info("cmd_loop begins")

        while self.broad_cast:

            self.log.debug("Waiting for new image to be available")
            await self.new_exposure_available.wait()

            if self._exposure is not None:
                self.log.debug(f"Sending image... {self._exposure.buffer}")
                writer.write(f"[START]\r\n".encode())
                writer.write(f"{self._exposure.width}\r\n".encode())
                writer.write(f"{self._exposure.height}\r\n".encode())
                writer.write(f"{int(self._exposure.isJPEG)}\r\n".encode())
                buffer = self._exposure.buffer.tobytes()
                writer.write(f"{len(buffer)}\r\n".encode())
                writer.write(buffer)
                writer.write(f"[END]\r\n".encode())
                await writer.drain()
            else:
                self.log.debug("No image to send")

            self.new_exposure_available.clear()
            self._exposure = None

    async def send_exposure(self, new_exposure):
        """ Broadcast an exposure to connected clients.

        Parameters
        ----------
        new_exposure : Exposure
            The exposure to send to the clients.
        """
        if self._server is None:
            raise RuntimeError("Server is not running.")

        async with self.bcast_lock:
            if self._exposure is not None:
                self.log.warning("Exposure not broadcasted yet. Overwriting.")

            self._exposure = new_exposure
            self.new_exposure_available.set()

    def _assertConnected(self):
        if not self.isConnected:
            raise ConnectionError()


class LiveViewClient:
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
            The port of the LiveViewServer to connect to.
        """
        self.log = logging.getLogger(__name__)
        self.ip = ip
        self.port = port
        self.sock = None
        self.reader = None
        self.isConnected = False

    def open(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.ip, self.port))
        self.sock.settimeout(30.)
        self.reader = self.sock.makefile(mode="rb")
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

        while True:
            try:
                read_bytes = self.reader.readline()

                if read_bytes.rstrip().endswith(b'[START]'):

                    self.log.debug(f"Image started... Got {read_bytes}")

                    read_bytes = self.reader.readline()
                    width = int(read_bytes.decode().rstrip())

                    read_bytes = self.reader.readline()
                    height = int(read_bytes.decode().rstrip())

                    read_bytes = self.reader.readline()
                    isJPEG = bool(int(read_bytes.decode().rstrip()))

                    read_bytes = self.reader.readline()
                    length = int(read_bytes.decode().rstrip())

                    self.log.debug(f"width: {width}, height: {height}, "
                                   f"isJpeg: {isJPEG}, length: {length}")

                    read_bytes = self.reader.readline()
                    buffer = read_bytes

                    while len(buffer) < length:
                        read_bytes = self.reader.readline()
                        buffer += read_bytes

                    dtype = np.uint8 if isJPEG else np.uint16

                    self.log.debug(f"Buffer size: {len(buffer)}")

                    return exposure.Exposure(np.frombuffer(buffer.rstrip()[:-5], dtype=dtype),
                                             width, height, {}, isJPEG)
                else:
                    self.log.debug(f"Got {read_bytes}. Expecting '>'.")

            except Exception as e:
                self.log.exception(e)
                self.log.warning("Reconnecting...")
                self.close()
                self.open()

    def _assertConnected(self):
        if not self.isConnected:
            raise ConnectionError()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncLiveViewClient:
    """This class defines an async live view client. It connects to
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
            The port of the LiveViewServer to connect to.
        """

        self.host = ip
        self.port = port
        self.connection_timeout = 30.

        self.connect_task = None
        self.reader = None
        self.writer = None

        self.log = logging.getLogger(__name__)

    async def start(self):
        self.connect_task = asyncio.open_connection(host=self.host, port=self.port)
        self.reader, self.writer = await asyncio.wait_for(self.connect_task,
                                                          timeout=self.connection_timeout)

    async def stop(self):
        """ Stop this connection to the LiveViewServer.
        """

        writer = self.writer
        self.reader = None
        self.writer = None
        if writer:
            try:
                writer.write_eof()
                await asyncio.wait_for(writer.drain(), timeout=2)
            finally:
                writer.close()

    async def receive_exposure(self):
        """Attempts to receive an exposure from the LiveViewServer.

        If a connection problem occurs then a ConnectionError is raised.
        If no image is available then an ImageReceiveError is raised.

        If for some reason the received image is corrupt then this
        method will attempt to re-sync to the sync code.

        Returns
        -------
        Exposure
            The exposure received from the LiveViewServer."""
        if self.reader is None:
            RuntimeError("Not connected to server.")

        while True:

            read_bytes = await self.reader.readline()

            if read_bytes.rstrip().endswith(b'[START]'):

                self.log.debug(f"Image started... Got {read_bytes}")

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.)
                width = int(read_bytes.decode().rstrip())

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.)
                height = int(read_bytes.decode().rstrip())

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.)
                isJPEG = bool(int(read_bytes.decode().rstrip()))

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.)
                length = int(read_bytes.decode().rstrip())

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.)
                buffer = read_bytes

                while len(buffer) < length:
                    read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.)
                    buffer += read_bytes

                dtype = np.uint8 if isJPEG else np.uint16

                return exposure.Exposure(np.frombuffer(buffer.rstrip()[:-5], dtype=dtype),
                                         width, height, {}, isJPEG)
            else:
                self.log.debug(f"Got {read_bytes}. Expecting '>'.")

    def _assertConnected(self):
        if not self.isConnected:
            raise ConnectionError()


class ImageReceiveError(Exception):
    def __init__(self):
        super().__init__()
