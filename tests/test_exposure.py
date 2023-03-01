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

import os
import pathlib
import tempfile
import unittest

import numpy as np
from astropy.io import fits
from lsst.ts.genericcamera import (
    Exposure,
    FitsHeaderItem,
    FitsHeaderItemsFromHeaderYaml,
    FitsHeaderItemsGenerator,
)

TEST_HEADER_DIR = pathlib.Path(__file__).parent / "data" / "header"


class TestExposure(unittest.TestCase):
    def setUp(self) -> None:
        self.hdul = None
        self.tmp_name = os.path.join(
            tempfile.gettempdir(), f"{next(tempfile._get_candidate_names())}.fits"
        )
        self.width = 1024
        self.height = 1024
        self.image = np.random.randint(
            low=np.iinfo(np.uint8).min,
            high=np.iinfo(np.uint8).max,
            size=(self.width, self.height),
            dtype=np.uint8,
        )

    def tearDown(self) -> None:
        if self.hdul:
            self.hdul.close()
        if os.path.exists(self.tmp_name):
            os.remove(self.tmp_name)

    def test(self):
        fhig = FitsHeaderItemsGenerator()
        tags = fhig.generate_fits_header_items()

        exp = Exposure(
            buffer=self.image,
            width=self.width,
            height=self.height,
            tags=tags,
        )

        self.assertIsNone(exp.header)
        exp.save(self.tmp_name)

        self.assertEqual(".fits", exp.suffix)

        self.assertTrue(
            os.path.exists(self.tmp_name), f"File {self.tmp_name} does not exist."
        )
        self.hdul = fits.open(self.tmp_name)
        hdr = self.hdul[0].header
        for tag in tags:
            self.assertIn(tag.name, hdr)

        exp.make_jpeg()
        self.assertTrue(exp.is_jpeg)
        self.assertEqual(".jpeg", exp.suffix)

    def testWithHeaderFile(self):
        exp = Exposure(
            buffer=self.image,
            width=self.width,
            height=self.height,
            tags=[FitsHeaderItem("ANSWER", 42, "Won't find this")],
        )

        header_file = TEST_HEADER_DIR / "header.yaml"
        fhifhy = FitsHeaderItemsFromHeaderYaml(header_file)
        exp.header = fhifhy.header_items
        self.assertIsNotNone(exp.header["PRIMARY"])

        exp.save(self.tmp_name)
        self.hdul = fits.open(self.tmp_name)
        self.assertIn("OBS-LAT", self.hdul[0].header)
        self.assertIn("INHERIT", self.hdul[1].header)
        self.assertEqual(
            f"[1:{self.height},1:{self.width}]", self.hdul[1].header["DETSIZE"]
        )
        self.assertNotIn("ANSWER", self.hdul[0].header)


if __name__ == "__main__":
    unittest.main()
