# This file is part of ts_GenericCamera.
#
# Developed for the LSST Telescope and Site Systems.
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
import tempfile
import numpy as np
import os

from lsst.ts.GenericCamera import Exposure


class TestExposure(unittest.TestCase):
    def test(self):

        width = 1024
        height = 1024
        image = np.random.randint(
            low=np.iinfo(np.uint8).min,
            high=np.iinfo(np.uint8).max,
            size=(width, height),
            dtype=np.uint8,
        )

        exp = Exposure(
            buffer=image, width=width, height=height, tags=["unit-test", "test", "unit"]
        )

        tmp_name = os.path.join(
            tempfile.gettempdir(), f"{next(tempfile._get_candidate_names())}.fits"
        )

        exp.save(tmp_name)

        self.assertTrue(os.path.exists(tmp_name), f"File {tmp_name} doe not exists.")

        exp.makeJPEG()

        self.assertTrue(exp.isJPEG)


if __name__ == "__main__":
    unittest.main()
