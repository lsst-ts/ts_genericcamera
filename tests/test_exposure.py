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
import tempfile
import numpy as np
import os

from astropy.io import fits

from lsst.ts.genericcamera import Exposure, FitsHeaderItemsGenerator, FitsHeaderTemplate


class TestExposure(unittest.TestCase):
    def setUp(self) -> None:
        self.hdul = None
        self.tmp_name = os.path.join(
            tempfile.gettempdir(), f"{next(tempfile._get_candidate_names())}.fits"
        )

    def tearDown(self) -> None:
        if self.hdul:
            self.hdul.close()
        if os.path.exists(self.tmp_name):
            os.remove(self.tmp_name)

    def test(self):
        fhig = FitsHeaderItemsGenerator()
        tags = fhig.generate_fits_header_items(FitsHeaderTemplate.ALL_SKY)
        width = 1024
        height = 1024
        image = np.random.randint(
            low=np.iinfo(np.uint8).min,
            high=np.iinfo(np.uint8).max,
            size=(width, height),
            dtype=np.uint8,
        )

        exp = Exposure(
            buffer=image,
            width=width,
            height=height,
            tags=tags,
        )

        exp.save(self.tmp_name)

        self.assertEqual(".fits", exp.suffix)

        self.assertTrue(
            os.path.exists(self.tmp_name), f"File {self.tmp_name} does not exist."
        )
        self.hdul = fits.open(self.tmp_name)
        hdr = self.hdul[0].header
        # Keep count of how often a header name has been processed becasue some
        # are double. The double ones mostly are empty names (i.e. '') but some
        # other double names exist as well.
        header_name_counts = {}

        for tag in tags:
            name = tag.name
            value = tag.value.replace("'", "")
            comment = tag.comment

            # Initialize the count for every name to 0 since astropy will
            # return the correct header item for all values >= 0.
            if name not in header_name_counts:
                header_name_counts[name] = 0

            # Get the current count and increase by one for the next iteration
            # of the loop.
            count = header_name_counts[name]
            header_name_counts[name] = count + 1

            self.assertEqual(
                hdr[(name, count)], value, f"Header value for {name} incorrect."
            )
            self.assertEqual(
                hdr.comments[(name, count)],
                comment,
                f"Header comment for {name} incorrect.",
            )

        exp.make_jpeg()
        self.assertTrue(exp.is_jpeg)
        self.assertEqual(".jpeg", exp.suffix)


if __name__ == "__main__":
    unittest.main()
