
import unittest
from unittest.mock import MagicMock

import asyncio
import yaml
import pathlib
import types

from lsst.ts.salobj.validator import DefaultingValidator

from lsst.ts.GenericCamera.driver import ASICamera


class Harness:

    def __init__(self):

        schema_path = pathlib.Path(__file__).resolve().parents[1].joinpath("schema",
                                                                           "GenericCamera.yaml")

        with open(schema_path, "r") as f:
            schema_data = f.read()

        schema = yaml.safe_load(schema_data)
        self.config_validator = DefaultingValidator(schema=schema)

        full_config_dict = self.config_validator.validate({'camera': 'Zwo',
                                                           'useZWOFilterWheel': False})

        self.config = types.SimpleNamespace(**full_config_dict)

        self.asicam = ASICamera()

        self.asicam.lib.openASI = MagicMock(return_value=MagicMock)

        self.asicam.lib.dev.getExposureStatus = MagicMock(return_value=3)

        self.asicam.initialise(self.config)

    async def take_image(self):

        await self.asicam.startTakeImage(expTime=1.,
                                         shutter=True,
                                         science=True,
                                         guide=True,
                                         wfs=True)

        await self.asicam.startShutterOpen()

        await self.asicam.endShutterOpen()

        await self.asicam.startIntegration()
        await self.asicam.endIntegration()

        await self.asicam.startShutterClose()

        await self.asicam.endShutterClose()

        await self.asicam.startReadout()

        exposure = await self.asicam.endReadout()

        await self.asicam.endTakeImage()

        return exposure


@unittest.skip("Under development")
class TestASICamera(unittest.TestCase):

    def testTakeImage(self):

        async def doit():

            harness = Harness()

            exposure = await harness.take_image()

            self.assertTrue(exposure is not None)
            self.assertTrue(not exposure.isJPEG)
            self.assertTrue(exposure.width == harness.asicam.maxWidth)
            self.assertTrue(exposure.height == harness.asicam.maxHeight)
            self.assertTrue(exposure.buffer is not None)

        asyncio.get_event_loop().run_until_complete(doit())


if __name__ == "__main__":
    unittest.main()
