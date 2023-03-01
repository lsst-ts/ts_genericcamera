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


import asyncio
import pathlib
import types
import unittest
from unittest.mock import MagicMock

import yaml
from lsst.ts.genericcamera.driver import ASICamera
from lsst.ts.salobj.validator import DefaultingValidator


class Harness:
    def __init__(self):
        schema_path = (
            pathlib.Path(__file__)
            .resolve()
            .parents[1]
            .joinpath("schema", "GenericCamera.yaml")
        )

        with open(schema_path, "r") as f:
            schema_data = f.read()

        schema = yaml.safe_load(schema_data)
        self.config_validator = DefaultingValidator(schema=schema)

        full_config_dict = self.config_validator.validate(
            {"camera": "Zwo", "useZWOFilterWheel": False}
        )

        self.config = types.SimpleNamespace(**full_config_dict)

        self.asicam = ASICamera()

        self.asicam.lib.openASI = MagicMock(return_value=MagicMock)

        self.asicam.lib.dev.getExposureStatus = MagicMock(return_value=3)

        self.asicam.initialise(self.config)

    async def take_image(self):
        await self.asicam.start_take_image(
            expTime=1.0, shutter=True, science=True, guide=True, wfs=True
        )

        await self.asicam.start_shutter_open()

        await self.asicam.end_shutter_open()

        await self.asicam.start_integration()
        await self.asicam.end_integration()

        await self.asicam.start_shutter_close()

        await self.asicam.end_shutter_close()

        await self.asicam.start_readout()

        exposure = await self.asicam.end_readout()

        await self.asicam.end_take_image()

        return exposure


@unittest.skip("Under development")
class TestASICamera(unittest.TestCase):
    def testTakeImage(self):
        async def doit():
            harness = Harness()

            exposure = await harness.take_image()

            self.assertTrue(exposure is not None)
            self.assertTrue(not exposure.is_jpeg)
            self.assertTrue(exposure.width == harness.asicam.maxWidth)
            self.assertTrue(exposure.height == harness.asicam.maxHeight)
            self.assertTrue(exposure.buffer is not None)

        asyncio.get_event_loop().run_until_complete(doit())


if __name__ == "__main__":
    unittest.main()
