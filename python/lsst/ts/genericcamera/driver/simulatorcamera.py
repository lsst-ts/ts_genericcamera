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

__all__ = ["SimulatorCamera"]

import asyncio
import time

import lsst.ts.utils as ts_utils
import numpy as np
import yaml

from .. import exposure
from . import streamingbasecamera


class SimulatorCamera(streamingbasecamera.StreamingBaseCamera):
    def __init__(self, log=None):
        super().__init__(log=log)

        self.is_live_exposure = False
        self.max_width = 1024
        self.max_height = 1024
        self.top_pixel = 0
        self.left_pixel = 0
        self.width = self.max_width
        self.height = self.max_height
        self.bytes_per_pixel = 2
        self.image_buffer = None

        self.shutter_time = 0.5  # Time to open/close shutter
        self.shutter_steps = 10  # steps on opening shutter
        self.use_shutter = False
        self.shutter_state = (
            0  # State of the shutter 0 = Closed, self.shutter_steps = Open
        )

        self.exposure_time = 0.001
        self.exposure_steps = 10  # steps on exposing
        self.exposure_state = 0  # State of the exposure

        self.readout_time = 0.5  # Time to readout
        self.readout_steps = 10  # steps on reading out
        self.readout_state = 0  # State of the reading out

        self.exposure_task = None

        self.isbusy_lock = asyncio.Lock()

        self.shutter_open_start_event = asyncio.Event()
        self.shutter_open_finish_event = asyncio.Event()

        self.exposure_start_event = asyncio.Event()
        self.exposure_finish_event = asyncio.Event()

        self.shutter_close_start_event = asyncio.Event()
        self.shutter_close_finish_event = asyncio.Event()

        self.readout_start_event = asyncio.Event()
        self.readout_finish_event = asyncio.Event()

        self.streaming_time_sleep = 0
        self.streaming_frames_size = 10
        self.streaming_frames = [_ for _ in range(self.streaming_frames_size)]

    @staticmethod
    def name():
        """Set camera name."""
        return "Simulator"

    def initialise(self, config):
        """Initialise the camera with the specified configuration file.

        Parameters
        ----------
        config : str
            The name of the configuration file to load."""
        pass

    def get_config_schema(self):
        return yaml.safe_load(
            """
$schema: http://json-schema.org/draft-07/schema#
description: Schema for Simulator cameras.
type: object
properties:
  max_width:
    type: number
    description: The maximum width of the image to produce in number of pixels.
    default: 1024
    minimum: 1024
    maximum: 2048
  max_height:
    type: number
    description: The maximum height of the image to produce in number of pixels.
    default: 1024
    minimum: 1024
    maximum: 2048
"""
        )

    def get_make_and_model(self):
        """Get the make and model of the camera.

        Returns
        -------
        str
            The make and model of the camera."""
        return "Simulator"

    def get_value(self, key):
        """Gets the value of a unique property of the camera.

        Parameters
        ----------
        key : str
            The name of the property.
        Returns
        -------
        str
            The value of the property.
            Returns 'UNDEFINED' if the property doesn't exist."""
        return super().get_value(key)

    async def set_value(self, key, value):
        """Set a unique property of the camera.

        Parameters
        ----------
        key : str
            The name of the property.
        value : str
            The value of the property."""
        key = key.lower()
        await super().set_value(key, value)

    def get_roi(self):
        """Gets the region of interest.

        Returns
        -------
        int
            The top most pixel of the region.
        int
            The left most pixel of the region.
        int
            The width of the region in pixels.
        int
            The height of the region in pixels."""
        return self.top_pixel, self.left_pixel, self.width, self.height

    def set_roi(self, top, left, width, height):
        """Sets the region of interest.

        Parameters
        ----------
        top : int
            The top most pixel of the region.
        left : int
            The left most pixel of the region.
        width : int
            The width of the region in pixels.
        height : int
            The height of the region in pixels."""
        self.top_pixel = top
        self.left_pixel = left
        self.width = width
        self.height = height

    def set_full_frame(self):
        """Sets the region of interest to the whole sensor."""
        self.set_roi(0, 0, self.max_width, self.max_height)

    def start_live_view(self):
        """Configure the camera for live view.

        This should change the image format to 8bits per pixel so
        the image can be encoded to JPEG."""
        self.bytes_per_pixel = 1
        self.is_live_exposure = True
        super().start_live_view()

    def stop_live_view(self):
        """Configure the camera for a standard exposure."""
        self.bytes_per_pixel = 2
        self.is_live_exposure = False
        super().stop_live_view()

    async def start_shutter_open(self):
        """Start opening the shutter.

        Check that shutter_task is not running and schedule open_shutter task
        to the event loop.
        """
        tasks = [self.exposure_task, self.shutter_open_start_event.wait()]

        for f in asyncio.as_completed(tasks):
            await f
            break
        await super().start_shutter_open()

    async def end_shutter_open(self):
        """End opening the shutter.

        Check that shutter_task is running and await for it to finish.
        """
        tasks = [self.shutter_open_finish_event.wait(), self.exposure_task]

        for f in asyncio.as_completed(tasks):
            await f
            break

    async def start_shutter_close(self):
        """Start closing the shutter.

        Check that shutter_task is not running and schedule close_shutter task
        to the event loop.
        """
        tasks = [self.exposure_task, self.shutter_close_start_event.wait()]

        for f in asyncio.as_completed(tasks):
            await f
            break

    async def end_shutter_close(self):
        """End closing the shutter.

        If the camera does have a shutter then this should wait for
        the shutter to finishing closing.

        If the camera doesn't have a shutter then don't do anything.
        """
        tasks = [self.exposure_task, self.shutter_close_finish_event.wait()]

        for f in asyncio.as_completed(tasks):
            await f
            break
        await super().end_shutter_close()

    async def start_take_image(self, exp_time, shutter, science, guide, wfs):
        """Start taking an image or a set of images.

        Parameters
        ----------
        exp_time : float
            The exposure time in seconds.
        shutter : bool
            Should the shutter be opened?
        science : bool
            Should the science/main sensor be used?
        guide : bool
            Should guider sensor be used?
        wfs : bool
            Should wave front sensor be used?
        """
        if self.exposure_task is not None and not self.exposure_task.done():
            raise RuntimeError("Exposure task running.")

        self.exposure_time = exp_time
        self.use_shutter = shutter

        self.log.debug("Cleaning events.")
        self.shutter_open_start_event.clear()
        self.shutter_open_finish_event.clear()
        self.exposure_start_event.clear()
        self.exposure_finish_event.clear()
        self.readout_start_event.clear()
        self.readout_finish_event.clear()
        self.shutter_close_start_event.clear()
        self.shutter_close_finish_event.clear()

        async with self.isbusy_lock:
            self.exposure_task = asyncio.ensure_future(self.simulate_exposure())

        await super().start_take_image(
            exp_time=exp_time, shutter=shutter, science=science, guide=guide, wfs=wfs
        )

    async def end_take_image(self):
        """End take image or images."""
        await self.exposure_task

        self.exposure_task = None

    async def start_integration(self):
        """Start integrating."""
        tasks = [self.exposure_task, self.exposure_start_event.wait()]

        for f in asyncio.as_completed(tasks):
            await f
            break

        await super().start_integration()

    async def end_integration(self):
        """End integration.

        This should wait for the integration period to complete."""
        tasks = [self.exposure_task, self.exposure_finish_event.wait()]

        for f in asyncio.as_completed(tasks):
            await f
            break

        await super().end_integration()

    async def start_readout(self):
        """Start reading out the image."""
        tasks = [self.exposure_task, self.readout_start_event.wait()]

        for f in asyncio.as_completed(tasks):
            await f
            break

        await super().start_readout()

    async def end_readout(self):
        """Start reading out the image."""
        tasks = [self.exposure_task, self.readout_finish_event.wait()]

        for f in asyncio.as_completed(tasks):
            await f
            break

        await self._set_tag_values()
        image = exposure.Exposure(self.image_buffer, self.width, self.height, self.tags)
        return image

    async def simulate_exposure(self):
        """This method will simulate all steps of exposure asynchronously,
        issuing events as each step goes on.
        """

        async with self.isbusy_lock:
            # Note that open shutter events will only be issued if shutter
            # is in use
            if self.use_shutter:
                self.log.debug("Open shutter.")
                await self.open_shutter()

            self.log.debug("Exposing.")
            await self.expose()

            # Note that close shutter events will only be issued if shutter
            # is in use
            if self.use_shutter:
                self.log.debug("Closing shutter.")
                await self.close_shutter()

            self.log.debug("Reading out.")
            await self.readout()

            self.log.debug("Done taking simulated exposure.")

    async def open_shutter(self):
        """Mimics task of opening the shutter."""

        if self.shutter_state == self.shutter_steps:
            raise RuntimeError("Shutter already open.")
        elif self.shutter_state != 0:
            raise RuntimeError(
                f"Shutter state is {self.shutter_state}. " f"Expected 0."
            )

        self.shutter_open_start_event.set()

        while self.shutter_state < self.shutter_steps:
            self.shutter_state += 1
            await asyncio.sleep(self.shutter_time / self.shutter_steps)

        self.shutter_open_finish_event.set()

    async def close_shutter(self):
        """Mimics task of opening the shutter."""
        if self.shutter_state == 0:
            raise RuntimeError("Shutter already closed.")

        self.shutter_close_start_event.set()

        while self.shutter_state > 0:
            self.shutter_state -= 1
            await asyncio.sleep(self.shutter_time / self.shutter_steps)

        self.shutter_close_finish_event.set()

    async def expose(self):
        """Mimics exposure."""

        if self.exposure_state != 0:
            raise RuntimeError("Ongoing exposure.")

        if self.exposure_time > 0.0:
            self.exposure_start_event.set()

            # imageByteCount = self.width * self.height * self.bytes_per_pixel
            buffer = np.random.randint(
                low=np.iinfo(np.uint16).min,
                high=np.iinfo(np.uint16).max,
                size=self.width * self.height,
                dtype=np.uint16,
            )
            self.log.debug(f"expose: {self.exposure_time}s.")

            self.image_buffer = buffer

            while self.exposure_state < self.exposure_steps:
                self.exposure_state += 1
                self.log.debug(
                    f"Exposure steps {self.exposure_state}/{self.exposure_steps}."
                )
                await asyncio.sleep(self.exposure_time / self.exposure_steps)

            self.exposure_finish_event.set()

        else:
            self.log.debug("Taking zero second exposure.")
            self.exposure_start_event.set()
            # imageByteCount = self.width * self.height * self.bytes_per_pixel
            self.image_buffer = np.zeros(self.width * self.height, dtype=np.uint16)
            self.exposure_state = self.exposure_steps
            self.exposure_finish_event.set()

    async def readout(self):
        """Mimic readout."""

        if self.readout_state != 0:
            raise RuntimeError("Ongoing readout!")
        elif not self.exposure_state == self.exposure_steps:
            raise RuntimeError(
                f"Exposure not completed! State {self.exposure_state}, "
                f"expected {self.exposure_steps}."
            )

        self.readout_start_event.set()

        while self.readout_state < self.readout_steps:
            self.readout_state += 1
            await asyncio.sleep(self.readout_time / self.readout_steps)
        self.readout_finish_event.set()
        # Reset exposure state
        self.exposure_state = 0

        # Reset readout state
        self.readout_state = 0

    def start_streaming_mode(self, exp_time: float, static_data: dict) -> None:
        """Start image streaming mode for the camera.

        Parameters
        ----------
        exp_time : float
            The exposure time in seconds.
        static_data : `dict`
            Data for header keywords.
        """
        super().start_streaming_mode(exp_time, static_data)
        self.log.info("In simulation camera start_streaming_mode")
        self.tick_frequency = 10**9
        self._generate_frames()
        self._set_information_for_streaming()

    def _generate_frames(self) -> None:
        """Generate frames for streaming mode"""
        _, _, width, height = self.get_roi()
        frame_size = width * height
        for i in range(self.streaming_frames_size):
            buffer = np.random.randint(
                low=np.iinfo(np.uint16).min,
                high=np.iinfo(np.uint16).max,
                size=frame_size,
                dtype=np.uint16,
            )
            self.streaming_frames[i] = buffer

    def _run_streaming(self) -> None:
        """Keep streaming mode for the camera alive."""
        self.log.info("Running _run_streaming")
        self._set_streaming_start_information()
        start_time = time.monotonic_ns()
        width, height = self.streaming_roi[2:]
        streaming_sleep_time = self.set_streaming_sleep_time(width, height)
        frame = 1
        while self.run_streaming_task:
            item = (
                frame,
                (
                    self.streaming_frames[(frame - 1) % self.streaming_frames_size],
                    width,
                    height,
                    time.monotonic_ns() - start_time,
                ),
            )
            handle = asyncio.run_coroutine_threadsafe(self.queue.put(item), self.loop)
            self.handles.append(handle)
            time.sleep(streaming_sleep_time)
            frame += 1
        else:
            self.streaming_mode_stop = ts_utils.current_tai()

    def set_streaming_sleep_time(self, width: int, height: int) -> float:
        """Set the sleep time for streaming mode.

        Parameters
        ----------
        width: `int`
            Image width
        height: `int`
            Image height

        Returns
        -------
        sleep_time: `float`
            The sleep time required to run the streaming mode at a
            particular frequency.
        """
        sleep_time = 1 / 50
        readout_time = 0.00009
        size = width * height

        if size >= (1024 * 1024):
            sleep_time = 1 / 60
        elif size >= (640 * 480):
            sleep_time = 1 / 90
        elif size >= (200 * 200):
            sleep_time = 1 / 180
        elif size >= (150 * 150):
            sleep_time = 1 / 230
        elif size >= (100 * 100):
            sleep_time = 1 / 300
        elif size >= (50 * 50):
            sleep_time = 1 / 430
        return max(sleep_time, self.exposure_time) + readout_time

    def get_camera_info(self) -> dict:
        """Provide camera specific configuration for logevent_cameraInfo.

        Returns
        -------
        `dict`
            Dictionary of topic attribute name (key) and value for attribute.
            Example: {"lensDiameter": 50.0}
        """
        return {"lensFocalLength": 100.0, "lensDiameter": 50.0}

    async def _set_tag_values(self):
        """Convenience coroutine to provide values for some of the tags in the
        FITS header. More tags can be added if necessary but these were deemed
        sufficient for unit testing."""
        await super()._set_tag_values()

        self.get_tag(name="EXPTIME").value = self.exposure_time
        self.get_tag(name="ISO").value = 100
