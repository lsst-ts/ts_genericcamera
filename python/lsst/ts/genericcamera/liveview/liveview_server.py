#!/usr/bin/env python3

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

import argparse
import os
import time
import asyncio

import numpy as np

import tornado.ioloop
import tornado.web
import tornado.websocket

from PIL import Image

from lsst.ts.genericcamera import AsyncLiveViewClient


def main():
    parser = argparse.ArgumentParser(description="Start the PyImageStream server.")

    parser.add_argument(
        "--s-port", default=8888, type=int, help="Web server port (default: 8888)"
    )
    parser.add_argument("--s-host", default="0.0.0.0", type=str, help="Host")
    parser.add_argument(
        "--c-port", default=8888, type=int, help="Web server port (default: 8888)"
    )
    parser.add_argument("--c-host", default="0.0.0.0", type=str, help="Host")

    args = parser.parse_args()

    class Camera:
        def __init__(self, host, port):
            print("Initializing camera...")
            self.client = AsyncLiveViewClient(host, port)
            self.event_loop = asyncio.get_event_loop()
            self.event_loop.run_until_complete(self.client.start())

        async def get_jpeg_image_bytes(self):
            exposure = await self.client.receive_exposure()
            print("got Exposure!")
            as8 = exposure.buffer.astype(np.uint8)
            pimg = Image.fromarray(as8.reshape(exposure.height, exposure.width))
            pimg.save("/tmp/foo.jpeg")
            return "/tmp/foo.jpeg"

    camera = Camera(args.c_host, args.c_port)

    class MJPEGHandler(tornado.web.RequestHandler):
        async def get(self):
            # ioloop = tornado.ioloop.IOLoop.current()
            self.set_header(
                "Cache-Control",
                "no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0",
            )
            self.set_header("Connection", "close")
            self.set_header(
                "Content-Type",
                "multipart/x-mixed-replace;boundary=--boundarydonotcross",
            )
            self.set_header("Expires", "Mon, 3 Jan 2000 12:34:56 GMT")
            self.set_header("Pragma", "no-cache")
            self.served_image_timestamp = time.time()
            my_boundary = "--boundarydonotcross\n"
            while True:
                img = await camera.get_jpeg_image_bytes()
                interval = 1.0
                if self.served_image_timestamp + interval < time.time():
                    print("C")
                    self.write(my_boundary)
                    self.write("Content-type: image/jpeg\r\n")
                    self.write("Content-length: %s\r\n\r\n" % len(img))
                    self.write(str(img))
                    self.served_image_timestamp = time.time()
                    await self.flush()
                else:
                    pass
                    # This doesn't work without a callback and self.get causes
                    # weird things to happen.
                    # ioloop.add_timeout(ioloop.time() + interval, self.get)

    script_path = os.path.dirname(os.path.realpath(__file__))
    static_path = script_path + "/static/"

    app = tornado.web.Application(
        [
            (r"/livestream", MJPEGHandler),
            (
                r"/(.*)",
                tornado.web.StaticFileHandler,
                {"path": static_path, "default_filename": "index.html"},
            ),
        ]
    )
    app.listen(args.s_port)

    print("Starting server: http://localhost:" + str(args.s_port) + "/")

    tornado.ioloop.IOLoop.current().start()
