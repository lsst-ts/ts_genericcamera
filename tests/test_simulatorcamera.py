# This file is part of ts_GenericCamera.
#
# Developed for the LSST Data Management System.
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

import unittest
import asyncio

from lsst.ts.GenericCamera.driver import SimulatorCamera


class TestSimulatorCamera(unittest.TestCase):
    def testTakeImage(self):
        async def doit():

            simcam = SimulatorCamera()

            await simcam.startTakeImage(
                expTime=1.0, shutter=True, science=True, guide=True, wfs=True
            )

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
