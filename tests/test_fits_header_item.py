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

import pathlib
import unittest

from lsst.ts.genericcamera import (
    FitsHeaderItemsFromHeaderYaml,
    FitsHeaderItemsGenerator,
)

TEST_HEADER_DIR = pathlib.Path(__file__).parent / "data" / "header"


class TestFitsHeaderItem(unittest.TestCase):
    def test(self):
        fhig = FitsHeaderItemsGenerator()
        tags = fhig.generate_fits_header_items()
        self.assertEqual(len(tags), 6)


class TestFitsHeaderFromHeaderYaml(unittest.TestCase):
    def test(self):
        header_file = TEST_HEADER_DIR / "header.yaml"
        fhihy = FitsHeaderItemsFromHeaderYaml(header_file)
        # There should be two header blocks
        self.assertListEqual(list(fhihy.header_items.keys()), ["PRIMARY", "IMAGE1"])
        fhi = next(
            (tag for tag in fhihy.header_items["PRIMARY"] if tag.name == "IMGTYPE")
        )
        self.assertIsNotNone(fhi)
        self.assertTupleEqual(fhi(), ("IMGTYPE", "ENGTEST", "BIAS, DARK, FLAT, OBJECT"))
        fhi = next((tag for tag in fhihy.header_items["PRIMARY"] if tag.name == "RA"))
        self.assertIsNotNone(fhi)
        self.assertTupleEqual(
            fhi(), ("RA", None, "RA commanded from pointing component")
        )
        fhi = next(
            (tag for tag in fhihy.header_items["IMAGE1"] if tag.name == "DETSIZE")
        )
        self.assertIsNotNone(fhi)
        self.assertEqual("DETSIZE", fhi.name)
        self.assertIsNotNone(fhi.value)
