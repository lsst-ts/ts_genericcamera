#!/usr/bin/env python3

import argparse
import os
import time
import asyncio

import numpy as np

import tornado.ioloop
import tornado.web
import tornado.websocket

from PIL import Image

from lsst.ts.GenericCamera import AsyncLiveViewClient

parser = argparse.ArgumentParser(description="Start the PyImageStream server.")

parser.add_argument("--s-port", default=8888, type=int, help="Web server port (default: 8888)")
parser.add_argument("--s-host", default="0.0.0.0", type=str, help="Host")
parser.add_argument("--c-port", default=8888, type=int, help="Web server port (default: 8888)")
parser.add_argument("--c-host", default="0.0.0.0", type=str, help="Host")


args = parser.parse_args()


class Camera:
    def __init__(self, host, port):
        print("Initializing camera...")
        self.client = AsyncLiveViewClient(host, port)
        self.event_loop = asyncio.get_event_loop()
        self.event_loop.run_until_complete(self.client.start())

    def get_jpeg_image_bytes(self):
        exposure = self.event_loop.run_until_complete(self.client.receive_exposure())
        print("got Exposure!")
        as8 = exposure.buffer.astype(np.uint8)
        pimg = Image.fromarray(as8.reshape(exposure.height, exposure.width))
        pimg.save("/tmp/foo.jpeg")
        return "/tmp/foo.jpeg"


camera = Camera(args.c_host, args.c_port)


class MJPEGHandler(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    @tornado.gen.coroutine
    def get(self):
        ioloop = tornado.ioloop.IOLoop.current()
        self.set_header(
            "Cache-Control", "no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0"
        )
        self.set_header("Connection", "close")
        self.set_header("Content-Type", "multipart/x-mixed-replace;boundary=--boundarydonotcross")
        self.set_header("Expires", "Mon, 3 Jan 2000 12:34:56 GMT")
        self.set_header("Pragma", "no-cache")
        self.served_image_timestamp = time.time()
        my_boundary = "--boundarydonotcross\n"
        while True:
            img = camera.get_jpeg_image_bytes()
            interval = 1.0
            if self.served_image_timestamp + interval < time.time():
                self.write(my_boundary)
                self.write("Content-type: image/jpeg\r\n")
                self.write("Content-length: %s\r\n\r\n" % len(img))
                self.write(str(img))
                self.served_image_timestamp = time.time()
                yield tornado.gen.Task(self.flush)
            else:
                yield tornado.gen.Task(ioloop.add_timeout, ioloop.time() + interval)


script_path = os.path.dirname(os.path.realpath(__file__))
static_path = script_path + "/static/"

app = tornado.web.Application(
    [
        (r"/livestream", MJPEGHandler),
        (r"/(.*)", tornado.web.StaticFileHandler, {"path": static_path, "default_filename": "index.html"}),
    ]
)
app.listen(args.s_port)

print("Starting server: http://localhost:" + str(args.s_port) + "/")

tornado.ioloop.IOLoop.current().start()
