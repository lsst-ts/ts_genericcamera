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

__all__ = ["LiveViewServer", "LiveViewClient", "AsyncLiveViewClient"]

import asyncio
import socket
import logging

import numpy as np

from lsst.ts.genericcamera import exposure


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

        self._server = await asyncio.start_server(
            self.broadcast_loop, host=self.host, port=self.port
        )

    async def stop(self):
        """Stop the TCP/IP server."""
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
                writer.write("[START]\r\n".encode())
                writer.write(f"{self._exposure.width}\r\n".encode())
                writer.write(f"{self._exposure.height}\r\n".encode())
                writer.write(f"{int(self._exposure.is_jpeg)}\r\n".encode())
                buffer = self._exposure.buffer.tobytes()
                writer.write(f"{len(buffer)}\r\n".encode())
                writer.write(buffer)
                writer.write("[END]\r\n".encode())
                await writer.drain()
            else:
                self.log.debug("No image to send")

            self.new_exposure_available.clear()
            self._exposure = None

    async def send_exposure(self, new_exposure):
        """Broadcast an exposure to connected clients.

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

    def _assert_connected(self):
        if not self.is_connected:
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
            The port of the LiveViewServer to connect to."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((ip, port))
        self.sock.settimeout(0.02)
        self.is_connected = True

    def close(self):
        """Closes this connection to the LiveViewServer."""
        if self.is_connected:
            # self.sock.shutdown(socket.SHUT_RD)
            self.sock.close()
            self.is_connected = False

    def receive_exposure(self):
        """Attempts to receive an exposure from the LiveViewServer.

        If a connection problem occurs then a ConnectionError is raised.
        If no image is available then an ImageReceiveError is raised.

        If for some reason the received image is corrupt then this
        method will attempt to re-sync to the sync code.

        Returns
        -------
        Exposure
            The exposure received from the LiveViewServer."""
        self._assert_connected()
        try:
            sync = int.from_bytes(self.sock.recv(4), byteorder="big")
            while True:
                if sync == 0xCAFEF00D:
                    width = int.from_bytes(self.sock.recv(4), byteorder="big")
                    height = int.from_bytes(self.sock.recv(4), byteorder="big")
                    is_jpeg = bool(int.from_bytes(self.sock.recv(4), byteorder="big"))
                    length = int.from_bytes(self.sock.recv(4), byteorder="big")
                    if length > 0:
                        img_buffer = b""
                        while len(img_buffer) < length:
                            packet = self.sock.recv(length - len(img_buffer))
                            if not packet:
                                break
                            img_buffer += packet
                        if len(img_buffer) == length:
                            print("receive_exposure - return")
                            return exposure.Exposure(
                                img_buffer, width, height, {}, is_jpeg
                            )
                else:
                    value = int.from_bytes(self.sock.recv(1), byteorder="big")
                    sync = ((sync & 0x00FFFFFF) << 8) | value
        except Exception as e:
            self.is_connected = False
            raise e

    def _assert_connected(self):
        if not self.is_connected:
            raise ConnectionError()


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
        self.connection_timeout = 30.0

        self.connect_task = None
        self.reader = None
        self.writer = None

        self.log = logging.getLogger(__name__)

    async def start(self):
        self.connect_task = asyncio.open_connection(host=self.host, port=self.port)
        self.reader, self.writer = await asyncio.wait_for(
            self.connect_task, timeout=self.connection_timeout
        )

    async def stop(self):
        """Stop this connection to the LiveViewServer."""

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

            if read_bytes.rstrip().endswith(b"[START]"):

                self.log.debug(f"Image started... Got {read_bytes}")

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.0)
                width = int(read_bytes.decode().rstrip())

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.0)
                height = int(read_bytes.decode().rstrip())

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.0)
                is_jpeg = bool(int(read_bytes.decode().rstrip()))

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.0)
                length = int(read_bytes.decode().rstrip())

                read_bytes = await asyncio.wait_for(self.reader.readline(), timeout=2.0)
                buffer = read_bytes

                while len(buffer) < length:
                    read_bytes = await asyncio.wait_for(
                        self.reader.readline(), timeout=2.0
                    )
                    buffer += read_bytes

                dtype = np.uint8 if is_jpeg else np.uint16

                return exposure.Exposure(
                    np.frombuffer(buffer.rstrip()[:-5], dtype=dtype),
                    width,
                    height,
                    {},
                    is_jpeg,
                )
            else:
                self.log.debug(f"Got {read_bytes}. Expecting '>'.")

    def _assert_connected(self):
        if not self.is_connected:
            raise ConnectionError()


class ImageReceiveError(Exception):
    def __init__(self):
        super().__init__()
