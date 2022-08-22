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

from astropy.time import Time, TimeDelta

from lsst.ts.genericcamera import utils


class TestUtils(unittest.TestCase):
    def test_get_dayobs(self):
        timestamp = Time("2022-08-22T11:00:00", scale="utc", format="isot")
        self.assertEqual(utils.get_dayobs(timestamp.utc.unix), "20220821")
        timestamp += TimeDelta(3600, format="sec")
        self.assertEqual(utils.get_dayobs(timestamp.utc.unix), "20220822")
        timestamp += TimeDelta(12 * 3600, format="sec")
        self.assertEqual(utils.get_dayobs(timestamp.utc.unix), "20220822")


if __name__ == "__main__":
    unittest.main()
