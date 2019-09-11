import io
import os
import numpy as np
from PIL import Image
import logging

from lsst.ts.GenericCamera.liveview.base_camera import BaseCamera
from lsst.ts.GenericCamera import LiveViewClient


class Camera(BaseCamera):
    @staticmethod
    def frames():
        log = logging.getLogger(__name__)
        with LiveViewClient(os.environ["LIVEVIEW_HOST"], int(os.environ["LIVEVIEW_PORT"])) as lv:

            stream = io.BytesIO()
            while True:
                try:
                    exposure = lv.receiveExposure()
                except Exception as e:
                    log.exception(e)
                    continue
                as8 = exposure.buffer.astype(np.uint8)
                image = Image.fromarray(as8.reshape(exposure.height,
                                                    exposure.width))
                image.thumbnail((exposure.height,
                                 exposure.width))
                # image.thumbnail((128, 128))

                # image.save('/tmp/foo.jpeg')
                #
                # frame = open('/tmp/foo.jpeg', 'rb').read()

                image.save(stream, format="jpeg")

                # return current frame
                stream.seek(0)
                yield stream.read()

                # reset stream for next frame
                stream.seek(0)
                stream.truncate()
