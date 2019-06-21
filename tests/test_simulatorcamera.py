
import unittest
import asyncio

from lsst.ts.GenericCamera.driver import SimulatorCamera


class TestSimulatorCamera(unittest.TestCase):

    def testTakeImage(self):

        async def doit():

            simcam = SimulatorCamera()

            await simcam.startTakeImage(expTime=1.,
                                        shutter=True,
                                        science=True,
                                        guide=True,
                                        wfs=True)

            await simcam.startShutterOpen()

            await simcam.endShutterOpen()

            await simcam.startIntegration()
            await simcam.endIntegration()

            await simcam.startShutterClose()

            await simcam.endShutterClose()

            await simcam.startReadout()

            exposure = await simcam.endReadout()

            await simcam.endTakeImage()

            self.assertTrue(exposure is not None)
            self.assertTrue(not exposure.isJPEG)
            self.assertTrue(exposure.width == simcam.maxWidth)
            self.assertTrue(exposure.height == simcam.maxHeight)
            self.assertTrue(exposure.buffer is not None)

        asyncio.get_event_loop().run_until_complete(doit())


if __name__ == "__main__":
    unittest.main()
