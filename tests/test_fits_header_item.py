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

import unittest

from lsst.ts.genericcamera import (
    FitsHeaderItemsGenerator,
    FitsHeaderTemplate,
    HEADERS_DIR,
)


class TestFitsHeaderItem(unittest.TestCase):
    def test(self):
        all_sky_header_template = HEADERS_DIR / "allsky.header"
        with open(all_sky_header_template) as f:
            lines = f.read()
        fhig = FitsHeaderItemsGenerator()
        self.tags = fhig.generate_fits_header_items(FitsHeaderTemplate.ALL_SKY)
        for tag in self.tags:
            if tag.name != "":
                self.assertTrue(tag.name in lines)
            if tag.value != "":
                self.assertTrue(tag.value in lines)
            if tag.comment != "":
                self.assertTrue(tag.comment in lines)

        fhi = next((tag for tag in self.tags if tag.name == "FACILITY"))
        self.assertIsNotNone(fhi)
        self.assertEqual("FACILITY", fhi.name)
        self.assertEqual("Vera C. Rubin Observatory", fhi.value)
        self.assertEqual("Facility name", fhi.comment)
