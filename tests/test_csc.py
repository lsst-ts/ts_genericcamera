# This file is part of ts_GenericCamera.
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

import asyncio
import glob
import os
import pathlib
import yaml
import unittest

import numpy as np

from lsst.ts import salobj
from lsst.ts import GenericCamera

STD_TIMEOUT = 2  # standard command timeout (sec)
LONG_TIMEOUT = 20  # timeout for starting SAL components (sec)
TEST_CONFIG_DIR = pathlib.Path(__file__).parents[1].joinpath("tests", "data", "config")

port_generator = salobj.index_generator(imin=3200)


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
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

    def basic_make_csc(self, initial_state, config_dir, simulation_mode, **kwargs):
        return GenericCamera.GenericCameraCsc(
            initial_state=initial_state,
            config_dir=config_dir,
            simulation_mode=0,
            index=1,
        )

    async def test_default_config_dir(self):
        async with self.make_csc(initial_state=salobj.State.STANDBY):
            self.assertEqual(self.csc.summary_state, salobj.State.STANDBY)

            desired_config_pkg_name = "ts_config_ocs"
            desired_config_env_name = desired_config_pkg_name.upper() + "_DIR"
            desired_config_pkg_dir = os.environ[desired_config_env_name]
            desired_config_dir = (
                pathlib.Path(desired_config_pkg_dir) / "GenericCamera/v1"
            )
            self.assertEqual(self.csc.get_config_pkg(), desired_config_pkg_name)
            self.assertEqual(self.csc.config_dir, desired_config_dir)

    async def test_configuration(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            self.assertEqual(self.csc.summary_state, salobj.State.STANDBY)
            state = await self.remote.evt_summaryState.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertEqual(state.summaryState, salobj.State.STANDBY)

            invalid_files = glob.glob(os.path.join(TEST_CONFIG_DIR, "invalid_*.yaml"))
            bad_config_names = [os.path.basename(name) for name in invalid_files]
            bad_config_names.append("no_such_file.yaml")
            for bad_config_name in bad_config_names:
                with self.subTest(bad_config_name=bad_config_name):
                    self.remote.cmd_start.set(settingsToApply=bad_config_name)
                    with self.assertRaises(salobj.AckError):
                        await self.remote.cmd_start.start(timeout=STD_TIMEOUT)

            self.remote.cmd_start.set(settingsToApply="all_fields")
            await self.remote.cmd_start.start(timeout=STD_TIMEOUT)
            self.assertEqual(self.csc.summary_state, salobj.State.DISABLED)
            state = await self.remote.evt_summaryState.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertEqual(state.summaryState, salobj.State.DISABLED)
            all_fields_path = os.path.join(TEST_CONFIG_DIR, "all_fields.yaml")
            with open(all_fields_path, "r") as f:
                all_fields_raw = f.read()
            all_fields_data = yaml.safe_load(all_fields_raw)
            for field, value in all_fields_data.items():
                self.assertEqual(getattr(self.csc.config, field), value)

    async def test_state_transition(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):

            async def check_rejected(expected_state):
                self.assertEqual(self.csc.summary_state, expected_state)
                csc_state = await self.remote.evt_summaryState.next(
                    flush=False, timeout=LONG_TIMEOUT
                )
                self.assertEqual(csc_state.summaryState, expected_state)

                extra_commands = (
                    "setROI",
                    "setFullFrame",
                    "startLiveView",
                    "stopLiveView",
                    "takeImages",
                )

                for bad_command in extra_commands:
                    with self.subTest(bad_command=bad_command):
                        cmd_attr = getattr(self.remote, f"cmd_{bad_command}")
                        with self.assertRaises(salobj.AckError):
                            await cmd_attr.start(cmd_attr.DataType(), timeout=1.0)

            await check_rejected(salobj.State.STANDBY)

            await salobj.set_summary_state(self.remote, salobj.State.DISABLED)

            await check_rejected(salobj.State.DISABLED)

            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)

            self.assertEqual(self.csc.summary_state, salobj.State.ENABLED)
            state = await self.remote.evt_summaryState.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertEqual(state.summaryState, salobj.State.ENABLED)

            await salobj.set_summary_state(self.remote, salobj.State.DISABLED)

            await check_rejected(salobj.State.DISABLED)

            await salobj.set_summary_state(self.remote, salobj.State.STANDBY)

            await check_rejected(salobj.State.STANDBY)

    async def test_take_image(self):
        async def take_bias():
            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=0.0,
                shutter=False,
                sensors="",
                keyValueMap="",
                obsNote="bias",
            )

            startTakeImage = await self.remote.evt_startTakeImage.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startTakeImage)

            with self.assertRaises(asyncio.TimeoutError):
                await self.remote.evt_startShutterOpen.next(
                    flush=False, timeout=LONG_TIMEOUT
                )

            with self.assertRaises(asyncio.TimeoutError):
                await self.remote.evt_endShutterOpen.next(
                    flush=False, timeout=LONG_TIMEOUT
                )

            startIntegration = await self.remote.evt_startIntegration.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startIntegration)

            endIntegration = await self.remote.evt_endIntegration.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(endIntegration)

            with self.assertRaises(asyncio.TimeoutError):
                await self.remote.evt_startShutterClose.next(
                    flush=False, timeout=LONG_TIMEOUT
                )

            with self.assertRaises(asyncio.TimeoutError):
                await self.remote.evt_endShutterClose.next(
                    flush=False, timeout=LONG_TIMEOUT
                )

            startReadout = await self.remote.evt_startReadout.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startReadout)

            endReadout = await self.remote.evt_endReadout.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(endReadout)

            endTakeImage = await self.remote.evt_endTakeImage.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(endTakeImage)

        async def take_image():
            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=np.random.rand() + 1.0,
                shutter=True,
                sensors="",
                keyValueMap="",
                obsNote="image",
            )

            startTakeImage = await self.remote.evt_startTakeImage.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startTakeImage)

            startShutterOpen = await self.remote.evt_startShutterOpen.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(startShutterOpen)

            endShutterOpen = await self.remote.evt_endShutterOpen.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(endShutterOpen)

            startIntegration = await self.remote.evt_startIntegration.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startIntegration)

            endIntegration = await self.remote.evt_endIntegration.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(endIntegration)

            startShutterClose = await self.remote.evt_startShutterClose.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(startShutterClose)

            endShutterClose = await self.remote.evt_endShutterClose.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(endShutterClose)

            startReadout = await self.remote.evt_startReadout.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startReadout)

            endReadout = await self.remote.evt_endReadout.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(endReadout)

            endTakeImage = await self.remote.evt_endTakeImage.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(endTakeImage)

        async with self.make_csc(
            initial_state=salobj.State.ENABLED, config_dir=TEST_CONFIG_DIR
        ):

            state = await self.remote.evt_summaryState.next(
                flush=False, timeout=LONG_TIMEOUT
            )

            self.assertEqual(state.summaryState, salobj.State.ENABLED)

            self.flush_take_image_events()

            # Take 2 images with random exposure time
            with self.subTest(image="image1"):
                await take_image()

            with self.subTest(image="image2"):
                await take_image()

            # Try taking 2 bias
            with self.subTest(image="bias1"):
                await take_bias()

            with self.subTest(image="bias2"):
                await take_bias()

    async def test_live_view(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):

            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)

            self.flush_take_image_events()

            # Check that LiveView fails if exptime = 0
            with self.assertRaises(salobj.AckError):
                await self.remote.cmd_startLiveView.start()

            client = GenericCamera.AsyncLiveViewClient("127.0.0.1", 5013)

            # Start Liveview and get a series of images
            self.remote.evt_startLiveView.flush()
            await self.remote.cmd_startLiveView.set_start(expTime=1.0)

            lv_start = await self.remote.evt_startLiveView.next(
                flush=False, timeout=LONG_TIMEOUT
            )

            self.assertIsNotNone(lv_start)

            await client.start()

            r_exp = await client.receive_exposure()

            self.assertIsNotNone(r_exp)

            await self.remote.cmd_stopLiveView.start()

    async def test_version(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            await self.assert_next_sample(
                self.remote.evt_softwareVersions,
                cscVersion=GenericCamera.__version__,
                subsystemVersions="",
            )
