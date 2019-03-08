# This file is part of ts_GenericCamera.
#
# Developed for the LSST.
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

__all__ = ["GenericCameraCsc"]

import asyncio

from lsst.ts import salobj
import SALPY_GenericCamera
import GenericCameraInterface
import ZWOCamera


class GenericCameraCsc(salobj.BaseCsc):
    def __init__(self, publishIP, initial_state=salobj.State.STANDBY, initial_simulation_mode=0):
        super().__init__(SALPY_GenericCamera, index=0, initial_state=initial_state,
                         initial_simulation_mode=initial_simulation_mode)
        self.telemetry_period = 0.05
        self.salinfo.manager.setDebugLevel(0)
        self.ip = publishIP
        self.port = 5005
        self.camera = ZWOCamera.ASICamera()
        self.camera.initialise("")
        self.server = None

    def do_setExposureTime(self, id_data):
        self._assertNotLive()
        exposureTimeInSec = id_data.data.exposureTimeInSec
        print(f"Setting exposure time to {exposureTimeInSec} seconds.")
        self.camera.setExposureTime(exposureTimeInSec)
        data = self.evt_exposureTime.DataType()
        data.exposureTimeInSec = exposureTimeInSec
        self.evt_exposureTime.put(data)

    def do_setROI(self, id_data):
        self._assertNotLive()
        top = id_data.data.topPixel
        left = id_data.data.leftPixel
        width = id_data.data.width
        height = id_data.data.height
        print(f"Setting roi to {top} {left} {width} {height}.")
        self.camera.setROI(top, left, width, height)
        data = self.evt_roi.DataType()
        data.topPixel = top
        data.leftPixel = left
        data.width = width
        data.height = height
        self.evt_roi.put(data)

    def do_setFullFrame(self, id_data):
        self._assertNotLive()
        print(f"Setting full frame.")
        self.camera.setFullFrame()

    async def do_takeExposure(self, id_data):
        self._assertNotLive()
        filePath = id_data.data.filePath
        print(f"Taking exposure to {filePath}.")
        exposure = await self.camera.takeExposure()
        exposure.save(filePath)

    def do_startLiveView(self, id_data):
        if self.server is None:
            self.camera.configureForLiveView()
            print(f"Starting live view on {self.port}.")
            self.server = GenericCameraInterface.LiveViewServer(self.port)
            data = self.evt_liveView.DataType()
            data.ip = self.ip
            data.port = self.port
            self.evt_liveView.put(data)

    def do_stopLiveView(self, id_data):
        if self.server is not None:
            print("Stopping live view.")
            self.camera.configureForExposure()
            self.server.close()
            self.server = None

    def report_summary_state(self):
        super().report_summary_state()
        if self.summary_state in (salobj.State.DISABLED, salobj.State.ENABLED):
            asyncio.ensure_future(self.telemetry_loop())

    async def telemetry_loop(self):
        while self.summary_state in (salobj.State.DISABLED, salobj.State.ENABLED):
            if self.server is not None:
                try:
                    self.server.checkForClients()
                    exposure = await self.camera.takeExposure()
                    exposure.makeJPEG()
                    if self.server is not None:
                        self.server.sendExposure(exposure)
                except Exception:
                    pass
            await asyncio.sleep(self.telemetry_period)

    async def _heartbeat_loop(self):
        """Output heartbeat at regular intervals.
        """
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                self.evt_heartbeat.put(self.evt_heartbeat.DataType())
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Heartbeat output failed: {e}", file=sys.stderr)

    def _assertNotLive(self):
        if self.server is not None:
            raise Exception()


if __name__ == '__main__':
    csc = GenericCameraCsc("127.0.0.1", initial_state=salobj.State.ENABLED)
    asyncio.get_event_loop().run_until_complete(csc.done_task)
