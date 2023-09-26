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

__all__ = ["StreamingBaseCamera"]

import asyncio
import concurrent
import copy

import lsst.ts.utils as ts_utils
from astropy.time import Time, TimeDelta

from .. import exposure
from . import basecamera


class StreamingBaseCamera(basecamera.BaseCamera):
    """This class describes behaviors for streamoing mode cameras."""

    def __init__(self, log):
        super().__init__(log=log)

        self.loop = asyncio.get_running_loop()
        self.executor = concurrent.futures.ThreadPoolExecutor()
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.run_streaming_task = False
        self.streaming_task = ts_utils.make_done_future()
        self.streaming_roi = None
        self.streaming_mode_start = 1
        self.streaming_mode_stop = 2
        self.frame_time_start = None
        self.exposure_time_delta = None
        self.frames_captured = 0
        self.tick_frequency = None
        self.static_data = {}
        # Extra tags for streaming mode
        self.get_tag(name="OBSID").comment = "Image name from image naming service"
        self.get_tag(
            name="DAYOBS"
        ).comment = "The observation day as defined by image name"
        self.get_tag(name="CAMCODE").comment = "The code for the camera"
        self.get_tag(
            name="CONTRLLR"
        ).comment = "The controller (e.g. O for OCS, C for CCS)"
        self.get_tag(
            name="CURINDEX"
        ).comment = "Index number for frame within the sequence"
        self.get_tag(name="MAXINDEX").comment = "Total number of frames in sequence"

    def start_streaming_mode(self, exp_time: float, static_data: dict) -> None:
        """Start image streaming mode for the camera.

        Parameters
        ----------
        exp_time : float
            The exposure time in seconds.
        static_data : `dict`
            Data for header keywords.
        """
        self.get_tag(name="EXPTIME").value = exp_time
        self.exposure_time_delta = TimeDelta(exp_time, scale="tai", format="sec")
        for key, value in static_data.items():
            self.get_tag(name=key).value = value

    def stop_streaming_mode(self) -> None:
        """Stop image streaming mode for the camera."""
        self.log.debug("Stopping camera streaming.")
        self.run_streaming_task = False
        self.log.debug(f"Is streaming task running: {self.streaming_task.running()}")
        concurrent.futures.wait([self.streaming_task], timeout=30)
        self.log.debug(f"Is streaming task done: {self.streaming_task.done()}")

    async def convert_streaming_frames(self) -> (int, exposure.Exposure):
        """Convert raw frames to exposures.

        Returns
        -------
        frame_num: `int`
            The integer number assigned to the streaming frame.
        exposure: `lsst.ts.genericcamera.Exposure`
            The exposure associated with the streaming frame.
        """
        frame_num, (
            frame_array,
            width,
            height,
            frame_timestamp,
        ) = await self.queue.get()

        offset = TimeDelta(
            frame_timestamp / self.tick_frequency, scale="tai", format="sec"
        )
        frame_begin = self.frame_time_start + offset
        frame_end = frame_begin + self.exposure_time_delta
        frame_begin_dt = frame_begin.to_datetime().isoformat()
        frame_end_dt = frame_end.to_datetime().isoformat()
        self.get_tag(name="DATE-OBS").value = frame_begin_dt
        self.get_tag(name="DATE-BEG").value = frame_begin_dt
        self.get_tag(name="DATE-END").value = frame_end_dt
        self.get_tag(name="CURINDEX").value = frame_num
        self.get_tag(name="MAXINDEX").value = self.frames_captured
        image = exposure.Exposure(frame_array, width, height, copy.deepcopy(self.tags))
        self.log.debug(
            f"Processing frame {frame_num} with timestamp: {frame_timestamp}"
        )
        self.queue.task_done()
        return frame_num, image

    async def _run_streaming(self) -> None:
        """Keep streaming mode for the camera alive."""
        raise NotImplementedError

    def _set_information_for_streaming(self) -> None:
        """Set information related to streaming mode."""
        self.streaming_roi = self.get_roi()
        self.run_streaming_task = True
        self.streaming_task = self.executor.submit(self._run_streaming)

    def _set_streaming_start_information(self) -> None:
        """Set information at the start of streaming."""
        self.streaming_mode_start = ts_utils.current_tai()
        self.frame_time_start = Time(
            self.streaming_mode_start, scale="tai", format="unix_tai"
        )
