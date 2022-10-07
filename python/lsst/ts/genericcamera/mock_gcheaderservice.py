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
from datetime import datetime
import logging

from lsst.ts import salobj

from . import utils

__all__ = ["MockGCHeaderService"]


class MockGCHeaderService(salobj.BaseCsc):
    """A limited GCHeaderService.

    Parameters
    ----------
    initial_state : `salobj.State` or `int` (optional)
        The initial state of the CSC. This is provided for unit testing,
        as real CSCs should start up in `State.STANDBY`, the default.
    """

    valid_simulation_modes = [0]
    version = "mock"

    def __init__(self, index, initial_state):
        super().__init__(
            name="GCHeaderService", index=index, initial_state=initial_state
        )
        self.genericcamera_remote = salobj.Remote(
            domain=self.domain, name="GenericCamera", index=index
        )
        self.genericcamera_remote.evt_startReadout.callback = (
            self.emit_largeFileObjectAvailable
        )
        self.test_header_list = None
        day_obs = utils.get_day_obs(datetime.utcnow().timestamp())
        self.test_take_image_header_list = [
            "GCHeaderService_header_GC1_O_20220822_000001.yaml",
            "GCHeaderService_header_GC1_O_20220822_000002.yaml",
            f"GCHeaderService_header_GC1_O_{day_obs}_000001.yaml",
            f"GCHeaderService_header_GC1_O_{day_obs}_000002.yaml",
            "GCHeaderService_header_GC1_O_20220822_000005.yaml",
            "GCHeaderService_header_GC1_O_20220822_000006.yaml",
        ]
        self.test_auto_exposure_header_list = [
            "GCHeaderService_header_GC1_O_20220830_000001.yaml",
            "GCHeaderService_header_GC1_O_20220830_000002.yaml",
            "GCHeaderService_header_GC1_O_20220830_000003.yaml",
            "GCHeaderService_header_GC1_O_20220830_000004.yaml",
        ]

    def set_take_image_list(self):
        self.test_header_list = self.test_take_image_header_list

    def set_auto_exposure_list(self):
        self.test_header_list = self.test_auto_exposure_header_list

    async def emit_largeFileObjectAvailable(self, data):
        logging.debug("Mock GCHeaderService: Sending LFOA")
        url = f"http://somepath/{self.test_header_list.pop(0)}"
        await self.evt_largeFileObjectAvailable.set_write(url=url, force_output=True)
