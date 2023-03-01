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

import numpy as np
from lsst.ts.genericcamera import AsyncLiveViewClient, Exposure, LiveViewServer


class TestLiveView(unittest.IsolatedAsyncioTestCase):
    def test(self):
        async def doit():
            width = 1024
            height = 1024

            # exp.make_jpeg()

            server = LiveViewServer(5013)

            client = AsyncLiveViewClient("127.0.0.1", 5013)

            await server.start()

            await client.start()

            for i in range(3):
                image = np.random.randint(
                    low=np.iinfo(np.uint16).min,
                    high=np.iinfo(np.uint16).max,
                    size=(width, height),
                    dtype=np.uint16,
                )

                exp = Exposure(
                    buffer=image,
                    width=width,
                    height=height,
                    tags=["unit-test", "test", "unit"],
                )

                await server.send_exposure(exp)

                r_exp = await client.receive_exposure()

                self.assertIsNotNone(r_exp)
                self.assertEqual(exp.width, r_exp.width)
                self.assertEqual(exp.height, r_exp.height)
                self.assertTrue(np.array_equal(exp.buffer, r_exp.buffer))

            await client.stop()

            await server.stop()

        asyncio.run(doit())


if __name__ == "__main__":
    unittest.main()
