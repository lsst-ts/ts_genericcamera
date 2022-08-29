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
import unittest

from lsst.ts.genericcamera.driver import SimulatorCamera
from lsst.ts.genericcamera.utils import DATETIME_FORMAT


class TestSimulatorCamera(unittest.IsolatedAsyncioTestCase):
    def testTakeImage(self):
        async def doit():

            simcam = SimulatorCamera()

            await simcam.start_take_image(
                exp_time=1.0, shutter=True, science=True, guide=True, wfs=True
            )

            await simcam.start_shutter_open()

            await simcam.end_shutter_open()

            await simcam.start_integration()
            await simcam.end_integration()

            await simcam.start_shutter_close()

            await simcam.end_shutter_close()

            await simcam.start_readout()

            exposure = await simcam.end_readout()

            await simcam.end_take_image()

            self.assertTrue(exposure is not None)
            self.assertTrue(not exposure.is_jpeg)
            self.assertTrue(exposure.width == simcam.max_width)
            self.assertTrue(exposure.height == simcam.max_height)
            self.assertTrue(exposure.buffer is not None)
            self.assertIsNotNone(simcam.datetime_start_readout)
            self.assertIsNotNone(simcam.datetime_end_readout)

            # Test several FITS header tags.
            self.assertEqual(
                simcam.get_tag("DATE-BEG").value,
                simcam.datetime_start_readout.strftime(DATETIME_FORMAT),
            )
            self.assertEqual(
                simcam.get_tag("DATE-END").value,
                simcam.datetime_end_readout.strftime(DATETIME_FORMAT),
            )
            self.assertEqual(simcam.get_tag("ISO").value, 100)

        asyncio.get_event_loop().run_until_complete(doit())


if __name__ == "__main__":
    unittest.main()
