# This file is part of ts_ATDome.
#
# Developed for the LSST Data Management System.
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

import asyncio
import glob
import os
import pathlib
import unittest
import yaml
import numpy as np
import logging

from lsst.ts import salobj
from lsst.ts import GenericCamera

STD_TIMEOUT = 2  # standard command timeout (sec)
LONG_TIMEOUT = 20  # timeout for starting SAL components (sec)
TEST_CONFIG_DIR = pathlib.Path(__file__).parents[1].joinpath("tests", "data", "config")

port_generator = salobj.index_generator(imin=3200)


class Harness:
    def __init__(self, initial_state, config_dir=None):
        salobj.test_utils.set_random_lsst_dds_domain()
        self.index = 1
        self.csc = GenericCamera.GenericCameraCsc(
            index=self.index, config_dir=config_dir,
            initial_state=initial_state,
            initial_simulation_mode=0)
        self.remote = salobj.Remote(domain=self.csc.domain, name="GenericCamera",
                                    index=self.index)
        self.csc.log.setLevel(logging.DEBUG)

    def flush_take_image_events(self):

        self.remote.evt_startTakeImage.flush()
        self.remote.evt_startShutterOpen.flush()
        self.remote.evt_endShutterOpen.flush()
        self.remote.evt_startIntegration.flush()
        self.remote.evt_endIntegration.flush()
        self.remote.evt_startShutterClose.flush()
        self.remote.evt_endShutterClose.flush()
        self.remote.evt_startReadout.flush()
        self.remote.evt_endReadout.flush()
        self.remote.evt_endTakeImage.flush()

    async def __aenter__(self):
        await self.csc.start_task
        await self.remote.start_task
        return self

    async def __aexit__(self, *args):
        await self.csc.close()


class CscTestCase(unittest.TestCase):
    def setUp(self):
        print()

    def test_default_config_dir(self):
        async def doit():
            async with Harness(initial_state=salobj.State.STANDBY) as harness:
                self.assertEqual(harness.csc.summary_state, salobj.State.STANDBY)

                desired_config_pkg_name = "ts_config_ocs"
                desired_config_env_name = desired_config_pkg_name.upper() + "_DIR"
                desird_config_pkg_dir = os.environ[desired_config_env_name]
                desired_config_dir = pathlib.Path(desird_config_pkg_dir) / "GenericCamera/v1"
                self.assertEqual(harness.csc.get_config_pkg(), desired_config_pkg_name)
                self.assertEqual(harness.csc.config_dir, desired_config_dir)

        asyncio.get_event_loop().run_until_complete(doit())

    def test_configuration(self):
        async def doit():
            async with Harness(initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR) as \
                    harness:
                self.assertEqual(harness.csc.summary_state, salobj.State.STANDBY)
                state = await harness.remote.evt_summaryState.next(flush=False,
                                                                   timeout=LONG_TIMEOUT)
                self.assertEqual(state.summaryState, salobj.State.STANDBY)

                invalid_files = glob.glob(os.path.join(TEST_CONFIG_DIR, "invalid_*.yaml"))
                bad_config_names = [os.path.basename(name) for name in invalid_files]
                bad_config_names.append("no_such_file.yaml")
                for bad_config_name in bad_config_names:
                    with self.subTest(bad_config_name=bad_config_name):
                        harness.remote.cmd_start.set(settingsToApply=bad_config_name)
                        with salobj.test_utils.assertRaisesAckError():
                            await harness.remote.cmd_start.start(timeout=STD_TIMEOUT)

                harness.remote.cmd_start.set(settingsToApply="all_fields")
                await harness.remote.cmd_start.start(timeout=STD_TIMEOUT)
                self.assertEqual(harness.csc.summary_state, salobj.State.DISABLED)
                state = await harness.remote.evt_summaryState.next(flush=False,
                                                                   timeout=STD_TIMEOUT)
                self.assertEqual(state.summaryState, salobj.State.DISABLED)
                all_fields_path = os.path.join(TEST_CONFIG_DIR, "all_fields.yaml")
                with open(all_fields_path, "r") as f:
                    all_fields_raw = f.read()
                all_fields_data = yaml.safe_load(all_fields_raw)
                for field, value in all_fields_data.items():
                    self.assertEqual(getattr(harness.csc.config, field), value)

        asyncio.get_event_loop().run_until_complete(doit())

    def test_state_transition(self):
        async def doit():
            async with Harness(initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR) as \
                    harness:

                async def check_rejected(expected_state):
                    self.assertEqual(harness.csc.summary_state, expected_state)
                    state = await harness.remote.evt_summaryState.next(flush=False,
                                                                       timeout=LONG_TIMEOUT)
                    self.assertEqual(state.summaryState, expected_state)

                    extra_commands = ("setROI",
                                      "setFullFrame",
                                      "startLiveView",
                                      "stopLiveView",
                                      "takeImages")

                    for bad_command in extra_commands:
                        with self.subTest(bad_command=bad_command):
                            cmd_attr = getattr(harness.remote, f"cmd_{bad_command}")
                            with self.assertRaises(salobj.AckError):
                                await cmd_attr.start(cmd_attr.DataType(), timeout=1.)

                await check_rejected(salobj.State.STANDBY)

                await salobj.set_summary_state(harness.remote, salobj.State.DISABLED)

                await check_rejected(salobj.State.DISABLED)

                await salobj.set_summary_state(harness.remote, salobj.State.ENABLED)

                self.assertEqual(harness.csc.summary_state, salobj.State.ENABLED)
                state = await harness.remote.evt_summaryState.next(flush=False,
                                                                   timeout=LONG_TIMEOUT)
                self.assertEqual(state.summaryState, salobj.State.ENABLED)

                await salobj.set_summary_state(harness.remote, salobj.State.DISABLED)

                await check_rejected(salobj.State.DISABLED)

                await salobj.set_summary_state(harness.remote, salobj.State.STANDBY)

                await check_rejected(salobj.State.STANDBY)

        asyncio.get_event_loop().run_until_complete(doit())

    def test_take_image(self):

        async def take_bias(harness):
            await harness.remote.cmd_takeImages.set_start(numImages=1,
                                                          expTime=0.,
                                                          shutter=False,
                                                          science=True,
                                                          guide=True,
                                                          wfs=True,
                                                          imageSequenceName="bias")

            startTakeImage = await harness.remote.evt_startTakeImage.next(flush=False,
                                                                          timeout=STD_TIMEOUT)
            self.assertIsNotNone(startTakeImage)

            with self.assertRaises(asyncio.TimeoutError):
                await harness.remote.evt_startShutterOpen.next(flush=False, timeout=LONG_TIMEOUT)

            with self.assertRaises(asyncio.TimeoutError):
                await harness.remote.evt_endShutterOpen.next(flush=False, timeout=LONG_TIMEOUT)

            startIntegration = await harness.remote.evt_startIntegration.next(flush=False,
                                                                              timeout=STD_TIMEOUT)
            self.assertIsNotNone(startIntegration)

            endIntegration = await harness.remote.evt_endIntegration.next(flush=False,
                                                                          timeout=LONG_TIMEOUT)
            self.assertIsNotNone(endIntegration)

            with self.assertRaises(asyncio.TimeoutError):
                await harness.remote.evt_startShutterClose.next(flush=False, timeout=LONG_TIMEOUT)

            with self.assertRaises(asyncio.TimeoutError):
                await harness.remote.evt_endShutterClose.next(flush=False, timeout=LONG_TIMEOUT)

            startReadout = await harness.remote.evt_startReadout.next(flush=False,
                                                                      timeout=STD_TIMEOUT)
            self.assertIsNotNone(startReadout)

            endReadout = await harness.remote.evt_endReadout.next(flush=False,
                                                                  timeout=STD_TIMEOUT)
            self.assertIsNotNone(endReadout)

            endTakeImage = await harness.remote.evt_endTakeImage.next(flush=False,
                                                                      timeout=STD_TIMEOUT)
            self.assertIsNotNone(endTakeImage)

        async def take_image(harness):
            await harness.remote.cmd_takeImages.set_start(numImages=1,
                                                          expTime=np.random.rand() + 1.,
                                                          shutter=True,
                                                          science=True,
                                                          guide=True,
                                                          wfs=True,
                                                          imageSequenceName="image")

            startTakeImage = await harness.remote.evt_startTakeImage.next(flush=False,
                                                                          timeout=STD_TIMEOUT)
            self.assertIsNotNone(startTakeImage)

            startShutterOpen = await harness.remote.evt_startShutterOpen.next(flush=False,
                                                                              timeout=LONG_TIMEOUT)
            self.assertIsNotNone(startShutterOpen)

            endShutterOpen = await harness.remote.evt_endShutterOpen.next(flush=False,
                                                                          timeout=LONG_TIMEOUT)
            self.assertIsNotNone(endShutterOpen)

            startIntegration = await harness.remote.evt_startIntegration.next(flush=False,
                                                                              timeout=STD_TIMEOUT)
            self.assertIsNotNone(startIntegration)

            endIntegration = await harness.remote.evt_endIntegration.next(flush=False,
                                                                          timeout=LONG_TIMEOUT)
            self.assertIsNotNone(endIntegration)

            startShutterClose = await harness.remote.evt_startShutterClose.next(
                flush=False, timeout=LONG_TIMEOUT)
            self.assertIsNotNone(startShutterClose)

            endShutterClose = await harness.remote.evt_endShutterClose.next(flush=False,
                                                                            timeout=LONG_TIMEOUT)
            self.assertIsNotNone(endShutterClose)

            startReadout = await harness.remote.evt_startReadout.next(flush=False,
                                                                      timeout=STD_TIMEOUT)
            self.assertIsNotNone(startReadout)

            endReadout = await harness.remote.evt_endReadout.next(flush=False,
                                                                  timeout=STD_TIMEOUT)
            self.assertIsNotNone(endReadout)

            endTakeImage = await harness.remote.evt_endTakeImage.next(flush=False,
                                                                      timeout=STD_TIMEOUT)
            self.assertIsNotNone(endTakeImage)

        async def doit():
            async with Harness(initial_state=salobj.State.ENABLED,
                               config_dir=TEST_CONFIG_DIR) as harness:

                state = await harness.remote.evt_summaryState.next(flush=False,
                                                                   timeout=LONG_TIMEOUT)

                self.assertEqual(state.summaryState, salobj.State.ENABLED)

                harness.flush_take_image_events()

                # Take 2 images with random exposure time
                with self.subTest(image='image1'):
                    await take_image(harness)

                with self.subTest(image='image2'):
                    await take_image(harness)

                # Try taking 2 bias
                with self.subTest(image='bias1'):
                    await take_bias(harness)

                with self.subTest(image='bias2'):
                    await take_bias(harness)

                # await take_bias(harness)

        asyncio.get_event_loop().run_until_complete(doit())

    def test_live_view(self):

        async def doit():
            async with Harness(initial_state=salobj.State.STANDBY,
                               config_dir=TEST_CONFIG_DIR) as harness:

                await salobj.set_summary_state(harness.remote, salobj.State.ENABLED)

                harness.flush_take_image_events()

                # Check that LiveView fails if exptime = 0
                with self.assertRaises(salobj.AckError):
                    await harness.remote.cmd_startLiveView.start()

                client = GenericCamera.AsyncLiveViewClient('127.0.0.1', 5013)

                # Start Liveview and get a series of images
                harness.remote.evt_startLiveView.flush()
                await harness.remote.cmd_startLiveView.set_start(expTime=1.)

                lv_start = await harness.remote.evt_startLiveView.next(flush=False,
                                                                       timeout=LONG_TIMEOUT)

                self.assertIsNotNone(lv_start)

                await client.start()

                r_exp = await client.receive_exposure()

                self.assertIsNotNone(r_exp)

                await harness.remote.cmd_stopLiveView.start()

        asyncio.get_event_loop().run_until_complete(doit())


if __name__ == "__main__":
    unittest.main()
