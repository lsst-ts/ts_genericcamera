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

import asyncio
import glob
import os
import pathlib
import unittest
import shutil

import numpy as np
from requests import ConnectionError
import yaml

from lsst.ts import salobj
from lsst.ts import genericcamera
from lsst.ts import utils

STD_TIMEOUT = 2  # standard command timeout (sec)
LONG_TIMEOUT = 20  # timeout for starting SAL components (sec)
TEST_CONFIG_DIR = pathlib.Path(__file__).parent / "data" / "config"


class CscTestCase(salobj.BaseCscTestCase, unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_dir = pathlib.Path.home() / "data"
        cls.data_dir.mkdir()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.data_dir)

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
        self.remote.evt_largeFileObjectAvailable.flush()
        self.remote.evt_endTakeImage.flush()

    def basic_make_csc(self, initial_state, config_dir, simulation_mode, **kwargs):
        return genericcamera.GenericCameraCsc(
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
                pathlib.Path(desired_config_pkg_dir) / "GenericCamera/v3"
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

            configs_available = await self.remote.evt_configurationsAvailable.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            overrides = [
                "all_fields.yaml",
                "invalid_bad_camera_driver.yaml",
                "invalid_malformed.yaml",
                "use_image_service.yaml",
            ]
            self.assertEqual(
                configs_available.overrides,
                ",".join(overrides),
            )

            invalid_files = glob.glob(os.path.join(TEST_CONFIG_DIR, "invalid_*.yaml"))
            bad_config_names = [os.path.basename(name) for name in invalid_files]
            bad_config_names.append("no_such_file.yaml")
            for bad_config_name in bad_config_names:
                with self.subTest(bad_config_name=bad_config_name):
                    self.remote.cmd_start.set(configurationOverride=bad_config_name)
                    with self.assertRaises(salobj.AckError):
                        await self.remote.cmd_start.start(timeout=STD_TIMEOUT)

            self.remote.cmd_start.set(configurationOverride="all_fields.yaml")
            await self.remote.cmd_start.start(timeout=STD_TIMEOUT)
            self.assertEqual(self.csc.summary_state, salobj.State.DISABLED)
            state = await self.remote.evt_summaryState.next(
                flush=False, timeout=STD_TIMEOUT
            )

            config_applied = await self.remote.evt_configurationApplied.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertEqual(
                config_applied.configurations, "_init.yaml,all_fields.yaml"
            )
            self.assertEqual(config_applied.otherInfo, "cameraInfo")
            camera_info = await self.remote.evt_cameraInfo.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertEqual(camera_info.cameraMakeAndModel, "Simulator")

            self.assertEqual(state.summaryState, salobj.State.DISABLED)
            all_fields_path = os.path.join(TEST_CONFIG_DIR, "all_fields.yaml")
            with open(all_fields_path, "r") as f:
                all_fields_raw = f.read()
            all_fields_data = yaml.safe_load(all_fields_raw)
            instance = all_fields_data["instances"][0]
            for field, value in instance.items():
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

        self.mock_response = unittest.mock.Mock()
        self.mock_response.status_code = 200
        self.mock_response.json.side_effect = [
            ["GC1_O_20220822_000001"],
            ["GC1_O_20220822_000002"],
            ["GC1_O_20220822_000005"],
        ]

        @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
        async def take_bias(mock_get):
            mock_get.side_effect = ConnectionError()

            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=0.0,
                shutter=False,
                sensors="",
                keyValueMap="imageType: BIAS, groupId: CALIBSET_20220823, testType: BIAS",
                obsNote="bias",
            )

            startTakeImage = await self.remote.evt_startTakeImage.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startTakeImage)

            with self.assertRaises(asyncio.TimeoutError):
                await self.remote.evt_startShutterOpen.next(
                    flush=False, timeout=STD_TIMEOUT
                )

            with self.assertRaises(asyncio.TimeoutError):
                await self.remote.evt_endShutterOpen.next(
                    flush=False, timeout=STD_TIMEOUT
                )

            startIntegration = await self.remote.evt_startIntegration.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startIntegration)
            self.assertEqual(
                startIntegration.additionalKeys,
                "imageType:groupId:testType:focalLength:diameter",
            )
            self.assertEqual(
                startIntegration.additionalValues, "BIAS:CALIBSET_20220823:BIAS:100:50"
            )

            endIntegration = await self.remote.evt_endIntegration.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(endIntegration)
            self.assertEqual(
                endIntegration.additionalKeys,
                "imageType:groupId:testType:focalLength:diameter",
            )
            self.assertEqual(
                endIntegration.additionalValues, "BIAS:CALIBSET_20220823:BIAS:100:50"
            )

            with self.assertRaises(asyncio.TimeoutError):
                await self.remote.evt_startShutterClose.next(
                    flush=False, timeout=STD_TIMEOUT
                )

            with self.assertRaises(asyncio.TimeoutError):
                await self.remote.evt_endShutterClose.next(
                    flush=False, timeout=STD_TIMEOUT
                )

            startReadout = await self.remote.evt_startReadout.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(startReadout)
            self.assertEqual(
                startReadout.additionalKeys,
                "imageType:groupId:testType:focalLength:diameter",
            )
            self.assertEqual(
                startReadout.additionalValues, "BIAS:CALIBSET_20220823:BIAS:100:50"
            )

            endReadout = await self.remote.evt_endReadout.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(endReadout)
            self.assertEqual(
                endReadout.additionalKeys,
                "imageType:groupId:testType:focalLength:diameter",
            )
            self.assertEqual(
                endReadout.additionalValues, "BIAS:CALIBSET_20220823:BIAS:100:50"
            )

            endTakeImage = await self.remote.evt_endTakeImage.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(endTakeImage)

        @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
        async def take_image(image_name_check, check_lfoa, mock_get):
            mock_get.return_value = self.mock_response
            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=np.random.rand() + 1.0,
                shutter=True,
                sensors="",
                keyValueMap="imageType: ENGTEST, groupId: TestGroup",
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
            self.assertEqual(startIntegration.imageSource, self.csc.image_source_short)
            self.assertEqual(
                startIntegration.imageController, self.csc.image_controller
            )
            self.assertEqual(
                startIntegration.imageNumber, self.csc.image_sequence_num - 1
            )
            self.assertEqual(startIntegration.imageDate, self.csc.dayobs)
            self.assertEqual(
                startIntegration.additionalKeys,
                "imageType:groupId:focalLength:diameter",
            )
            self.assertEqual(
                startIntegration.additionalValues, "ENGTEST:TestGroup:100:50"
            )
            self.assertEqual(startIntegration.imageName, image_name_check)

            endIntegration = await self.remote.evt_endIntegration.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(endIntegration)
            self.assertEqual(
                endIntegration.additionalKeys, "imageType:groupId:focalLength:diameter"
            )
            self.assertEqual(
                endIntegration.additionalValues, "ENGTEST:TestGroup:100:50"
            )

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
            self.assertEqual(startReadout.imageSource, self.csc.image_source_short)
            self.assertEqual(startReadout.imageController, self.csc.image_controller)
            self.assertEqual(startReadout.imageNumber, self.csc.image_sequence_num - 1)
            self.assertEqual(startReadout.imageDate, self.csc.dayobs)
            self.assertEqual(
                startReadout.additionalKeys, "imageType:groupId:focalLength:diameter"
            )
            self.assertEqual(startReadout.additionalValues, "ENGTEST:TestGroup:100:50")
            self.assertEqual(startReadout.imageName, image_name_check)

            endReadout = await self.remote.evt_endReadout.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(endReadout)
            self.assertEqual(endReadout.imageSource, self.csc.image_source_short)
            self.assertEqual(endReadout.imageController, self.csc.image_controller)
            self.assertEqual(endReadout.imageNumber, self.csc.image_sequence_num - 1)
            self.assertEqual(endReadout.imageDate, self.csc.dayobs)
            self.assertEqual(
                endReadout.additionalKeys, "imageType:groupId:focalLength:diameter"
            )
            self.assertEqual(endReadout.additionalValues, "ENGTEST:TestGroup:100:50")
            self.assertEqual(startReadout.imageName, image_name_check)

            if check_lfoa:
                largeFileObjectAvailable = (
                    await self.remote.evt_largeFileObjectAvailable.next(
                        flush=False, timeout=LONG_TIMEOUT
                    )
                )
                self.assertIsNotNone(largeFileObjectAvailable)

            endTakeImage = await self.remote.evt_endTakeImage.next(
                flush=False, timeout=STD_TIMEOUT
            )
            self.assertIsNotNone(endTakeImage)

        @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
        async def take_image_no_image_service(image_name_check, mock_get):
            mock_get.side_effect = ConnectionError("Cannot connect to image service")
            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=np.random.rand() + 1.0,
                shutter=True,
                sensors="",
                keyValueMap="imageType: ENGTEST, groupId: TestGroup",
                obsNote="image",
            )

        @unittest.mock.patch("lsst.ts.genericcamera.requests.get")
        async def take_image_image_service_bad_status_code(image_name_check, mock_get):
            self.mock_response.status_code = 400
            mock_get.return_value = self.mock_response
            await self.remote.cmd_takeImages.set_start(
                numImages=1,
                expTime=np.random.rand() + 1.0,
                shutter=True,
                sensors="",
                keyValueMap="imageType: ENGTEST, groupId: TestGroup",
                obsNote="image",
            )

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
                await take_image("GC1_O_20220822_000001")

            with self.subTest(image="image2"):
                await take_image("GC1_O_20220822_000002")

            # Try taking 2 bias
            with self.subTest(image="bias1"):
                await take_bias()

            with self.subTest(image="bias2"):
                await take_bias()

            await salobj.set_summary_state(self.remote, salobj.State.STANDBY)
            await salobj.set_summary_state(
                self.remote, salobj.State.ENABLED, override="use_image_service.yaml"
            )

            with self.subTest(image="image4"):
                await take_image("GC1_O_20220822_000005")

            with self.subTest(image="image5"):
                with self.assertRaises(salobj.AckError):
                    await take_image_no_image_service("")

            with self.subTest(image="image6"):
                with self.assertRaises(salobj.AckError):
                    await take_image_image_service_bad_status_code("")

        # Run with LFA
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            with utils.modify_environ(
                AWS_ACCESS_KEY_ID="test",
                AWS_SECRET_ACCESS_KEY="bar",
                MYS3_ACCESS_KEY="test",
                MYS3_SECRET_KEY="bar",
            ):
                await salobj.set_summary_state(
                    self.remote, salobj.State.ENABLED, override="mock_lfa.yaml"
                )
                self.flush_take_image_events()

                with self.subTest(image="image3"):
                    await take_image(check_lfoa=True)

    async def test_live_view(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):

            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)

            self.flush_take_image_events()

            # Check that LiveView fails if exptime = 0
            with self.assertRaises(salobj.AckError):
                await self.remote.cmd_startLiveView.start()

            client = genericcamera.AsyncLiveViewClient("127.0.0.1", 5013)

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

    async def test_auto_exposure(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):

            await salobj.set_summary_state(self.remote, salobj.State.ENABLED)

            # Set the auto exposure time interval to a low value so
            # the test doesn't take so long
            self.csc.config.auto_exposure_interval = 2.0

            self.flush_take_image_events()

            await self.remote.cmd_startAutoExposure.set_start(
                minExpTime=1.0, maxExpTime=10.0, configuration=""
            )
            ae_start = await self.remote.evt_autoExposureStarted.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(ae_start)

            ti_start = await self.remote.evt_startTakeImage.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(ti_start)
            ti_end = await self.remote.evt_endTakeImage.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(ti_end)

            ti_start = await self.remote.evt_startTakeImage.next(
                flush=False,
                timeout=LONG_TIMEOUT + 5,
            )
            self.assertIsNotNone(ti_start)
            ti_end = await self.remote.evt_endTakeImage.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(ti_end)

            await self.remote.cmd_stopAutoExposure.start()
            ae_stop = await self.remote.evt_autoExposureStopped.next(
                flush=False, timeout=LONG_TIMEOUT
            )
            self.assertIsNotNone(ae_stop)

    async def test_version(self):
        async with self.make_csc(
            initial_state=salobj.State.STANDBY, config_dir=TEST_CONFIG_DIR
        ):
            await self.assert_next_sample(
                self.remote.evt_softwareVersions,
                cscVersion=genericcamera.__version__,
                subsystemVersions="",
            )
