
import unittest
import asyncio
import numpy as np

from lsst.ts.GenericCamera import Exposure, LiveViewServer, AsyncLiveViewClient


class TestLiveView(unittest.TestCase):

    def test(self):

        async def doit():
            width = 1024
            height = 1024

            # exp.makeJPEG()

            server = LiveViewServer(5013)

            client = AsyncLiveViewClient('127.0.0.1', 5013)

            await server.start()

            await client.start()

            for i in range(10):
                image = np.random.randint(low=np.iinfo(np.uint16).min,
                                          high=np.iinfo(np.uint16).max,
                                          size=(width, height),
                                          dtype=np.uint16)

                exp = Exposure(buffer=image,
                               width=width,
                               height=height,
                               tags=["unit-test", "test", "unit"])

                await server.send_exposure(exp)

                r_exp = await client.receive_exposure()

                self.assertIsNotNone(r_exp)
                self.assertEqual(exp.width, r_exp.width)
                self.assertEqual(exp.height, r_exp.height)
                self.assertTrue(np.array_equal(exp.buffer, r_exp.buffer))

            await client.stop()

            await server.stop()

        asyncio.get_event_loop().run_until_complete(doit())


if __name__ == "__main__":
    unittest.main()
