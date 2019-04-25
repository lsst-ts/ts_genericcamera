# This file is part of GenericCamera.
#
# Developed for the LSST Telescope and Site Systems.
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
# along with this program.  If not, see <https://www.gnu.org/licenses/>.Controller

import time

import SALPY_GenericCamera


class GenericCameraController:
    def __init__(self, index=0):
        self.sal = SALPY_GenericCamera.SAL_GenericCamera(index)
        self.sal.setDebugLevel(0)
        self.sal.salProcessor("GenericCamera_command_abort")
        self.sal.salProcessor("GenericCamera_command_enable")
        self.sal.salProcessor("GenericCamera_command_disable")
        self.sal.salProcessor("GenericCamera_command_standby")
        self.sal.salProcessor("GenericCamera_command_exitControl")
        self.sal.salProcessor("GenericCamera_command_start")
        self.sal.salProcessor("GenericCamera_command_enterControl")
        self.sal.salProcessor("GenericCamera_command_setLogLevel")
        self.sal.salProcessor("GenericCamera_command_setSimulationMode")
        self.sal.salProcessor("GenericCamera_command_setValue")
        self.sal.salProcessor("GenericCamera_command_setROI")
        self.sal.salProcessor("GenericCamera_command_setFullFrame")
        self.sal.salProcessor("GenericCamera_command_startLiveView")
        self.sal.salProcessor("GenericCamera_command_stopLiveView")
        self.sal.salProcessor("GenericCamera_command_takeImages")

        self.sal.salEventPub("GenericCamera_logevent_settingVersions")
        self.sal.salEventPub("GenericCamera_logevent_errorCode")
        self.sal.salEventPub("GenericCamera_logevent_summaryState")
        self.sal.salEventPub("GenericCamera_logevent_appliedSettingsMatchStart")
        self.sal.salEventPub("GenericCamera_logevent_logLevel")
        self.sal.salEventPub("GenericCamera_logevent_logMessage")
        self.sal.salEventPub("GenericCamera_logevent_simulationMode")
        self.sal.salEventPub("GenericCamera_logevent_heartbeat")
        self.sal.salEventPub("GenericCamera_logevent_cameraInfo")
        self.sal.salEventPub("GenericCamera_logevent_cameraSpecificProperty")
        self.sal.salEventPub("GenericCamera_logevent_roi")
        self.sal.salEventPub("GenericCamera_logevent_startLiveView")
        self.sal.salEventPub("GenericCamera_logevent_endLiveView")
        self.sal.salEventPub("GenericCamera_logevent_startTakeImage")
        self.sal.salEventPub("GenericCamera_logevent_startShutterOpen")
        self.sal.salEventPub("GenericCamera_logevent_endShutterOpen")
        self.sal.salEventPub("GenericCamera_logevent_startIntegration")
        self.sal.salEventPub("GenericCamera_logevent_endIntegration")
        self.sal.salEventPub("GenericCamera_logevent_startShutterClose")
        self.sal.salEventPub("GenericCamera_logevent_endShutterClose")
        self.sal.salEventPub("GenericCamera_logevent_startReadout")
        self.sal.salEventPub("GenericCamera_logevent_endReadout")
        self.sal.salEventPub("GenericCamera_logevent_endTakeImage")

        self.sal.salTelemetryPub("GenericCamera_temperature")

        self.commandSubscribers_abort = []
        self.commandSubscribers_enable = []
        self.commandSubscribers_disable = []
        self.commandSubscribers_standby = []
        self.commandSubscribers_exitControl = []
        self.commandSubscribers_start = []
        self.commandSubscribers_enterControl = []
        self.commandSubscribers_setLogLevel = []
        self.commandSubscribers_setSimulationMode = []
        self.commandSubscribers_setValue = []
        self.commandSubscribers_setROI = []
        self.commandSubscribers_setFullFrame = []
        self.commandSubscribers_startLiveView = []
        self.commandSubscribers_stopLiveView = []
        self.commandSubscribers_takeImages = []

        self.previousEvent_settingVersions = SALPY_GenericCamera.GenericCamera_logevent_settingVersionsC()
        self.previousEvent_errorCode = SALPY_GenericCamera.GenericCamera_logevent_errorCodeC()
        self.previousEvent_summaryState = SALPY_GenericCamera.GenericCamera_logevent_summaryStateC()
        self.previousEvent_appliedSettingsMatchStart = SALPY_GenericCamera.GenericCamera_logevent_appliedSettingsMatchStartC()
        self.previousEvent_logLevel = SALPY_GenericCamera.GenericCamera_logevent_logLevelC()
        self.previousEvent_logMessage = SALPY_GenericCamera.GenericCamera_logevent_logMessageC()
        self.previousEvent_simulationMode = SALPY_GenericCamera.GenericCamera_logevent_simulationModeC()
        self.previousEvent_heartbeat = SALPY_GenericCamera.GenericCamera_logevent_heartbeatC()
        self.previousEvent_cameraInfo = SALPY_GenericCamera.GenericCamera_logevent_cameraInfoC()
        self.previousEvent_cameraSpecificProperty = SALPY_GenericCamera.GenericCamera_logevent_cameraSpecificPropertyC()
        self.previousEvent_roi = SALPY_GenericCamera.GenericCamera_logevent_roiC()
        self.previousEvent_startLiveView = SALPY_GenericCamera.GenericCamera_logevent_startLiveViewC()
        self.previousEvent_endLiveView = SALPY_GenericCamera.GenericCamera_logevent_endLiveViewC()
        self.previousEvent_startTakeImage = SALPY_GenericCamera.GenericCamera_logevent_startTakeImageC()
        self.previousEvent_startShutterOpen = SALPY_GenericCamera.GenericCamera_logevent_startShutterOpenC()
        self.previousEvent_endShutterOpen = SALPY_GenericCamera.GenericCamera_logevent_endShutterOpenC()
        self.previousEvent_startIntegration = SALPY_GenericCamera.GenericCamera_logevent_startIntegrationC()
        self.previousEvent_endIntegration = SALPY_GenericCamera.GenericCamera_logevent_endIntegrationC()
        self.previousEvent_startShutterClose = SALPY_GenericCamera.GenericCamera_logevent_startShutterCloseC()
        self.previousEvent_endShutterClose = SALPY_GenericCamera.GenericCamera_logevent_endShutterCloseC()
        self.previousEvent_startReadout = SALPY_GenericCamera.GenericCamera_logevent_startReadoutC()
        self.previousEvent_endReadout = SALPY_GenericCamera.GenericCamera_logevent_endReadoutC()
        self.previousEvent_endTakeImage = SALPY_GenericCamera.GenericCamera_logevent_endTakeImageC()

        self.topicsSubscribedToo = {}

    def close(self):
        time.sleep(1)
        self.sal.salShutdown()

    def flush(self, action):
        result, data = action()
        while result >= 0:
            result, data = action()

    def checkForSubscriber(self, action, subscribers):
        result, data = action()
        if result > 0:
            for subscriber in subscribers:
                subscriber(result, data)

    def runSubscriberChecks(self):
        for subscribedTopic in self.topicsSubscribedToo:
            action = self.topicsSubscribedToo[subscribedTopic][0]
            subscribers = self.topicsSubscribedToo[subscribedTopic][1]
            self.checkForSubscriber(action, subscribers)

    def getTimestamp(self):
        return self.sal.getCurrentTime()

    def acceptCommand_abort(self):
        data = SALPY_GenericCamera.GenericCamera_command_abortC()
        result = self.sal.acceptCommand_abort(data)
        return result, data

    def ackCommand_abort(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_abort(cmdId, ackCode, errorCode, description)

    def subscribeCommand_abort(self, action):
        self.commandSubscribers_abort.append(action)
        if "command_abort" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_abort"] = [self.acceptCommand_abort, self.commandSubscribers_abort]

    def acceptCommand_enable(self):
        data = SALPY_GenericCamera.GenericCamera_command_enableC()
        result = self.sal.acceptCommand_enable(data)
        return result, data

    def ackCommand_enable(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_enable(cmdId, ackCode, errorCode, description)

    def subscribeCommand_enable(self, action):
        self.commandSubscribers_enable.append(action)
        if "command_enable" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_enable"] = [self.acceptCommand_enable, self.commandSubscribers_enable]

    def acceptCommand_disable(self):
        data = SALPY_GenericCamera.GenericCamera_command_disableC()
        result = self.sal.acceptCommand_disable(data)
        return result, data

    def ackCommand_disable(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_disable(cmdId, ackCode, errorCode, description)

    def subscribeCommand_disable(self, action):
        self.commandSubscribers_disable.append(action)
        if "command_disable" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_disable"] = [self.acceptCommand_disable, self.commandSubscribers_disable]

    def acceptCommand_standby(self):
        data = SALPY_GenericCamera.GenericCamera_command_standbyC()
        result = self.sal.acceptCommand_standby(data)
        return result, data

    def ackCommand_standby(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_standby(cmdId, ackCode, errorCode, description)

    def subscribeCommand_standby(self, action):
        self.commandSubscribers_standby.append(action)
        if "command_standby" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_standby"] = [self.acceptCommand_standby, self.commandSubscribers_standby]

    def acceptCommand_exitControl(self):
        data = SALPY_GenericCamera.GenericCamera_command_exitControlC()
        result = self.sal.acceptCommand_exitControl(data)
        return result, data

    def ackCommand_exitControl(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_exitControl(cmdId, ackCode, errorCode, description)

    def subscribeCommand_exitControl(self, action):
        self.commandSubscribers_exitControl.append(action)
        if "command_exitControl" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_exitControl"] = [self.acceptCommand_exitControl, self.commandSubscribers_exitControl]

    def acceptCommand_start(self):
        data = SALPY_GenericCamera.GenericCamera_command_startC()
        result = self.sal.acceptCommand_start(data)
        return result, data

    def ackCommand_start(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_start(cmdId, ackCode, errorCode, description)

    def subscribeCommand_start(self, action):
        self.commandSubscribers_start.append(action)
        if "command_start" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_start"] = [self.acceptCommand_start, self.commandSubscribers_start]

    def acceptCommand_enterControl(self):
        data = SALPY_GenericCamera.GenericCamera_command_enterControlC()
        result = self.sal.acceptCommand_enterControl(data)
        return result, data

    def ackCommand_enterControl(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_enterControl(cmdId, ackCode, errorCode, description)

    def subscribeCommand_enterControl(self, action):
        self.commandSubscribers_enterControl.append(action)
        if "command_enterControl" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_enterControl"] = [self.acceptCommand_enterControl, self.commandSubscribers_enterControl]

    def acceptCommand_setLogLevel(self):
        data = SALPY_GenericCamera.GenericCamera_command_setLogLevelC()
        result = self.sal.acceptCommand_setLogLevel(data)
        return result, data

    def ackCommand_setLogLevel(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_setLogLevel(cmdId, ackCode, errorCode, description)

    def subscribeCommand_setLogLevel(self, action):
        self.commandSubscribers_setLogLevel.append(action)
        if "command_setLogLevel" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_setLogLevel"] = [self.acceptCommand_setLogLevel, self.commandSubscribers_setLogLevel]

    def acceptCommand_setSimulationMode(self):
        data = SALPY_GenericCamera.GenericCamera_command_setSimulationModeC()
        result = self.sal.acceptCommand_setSimulationMode(data)
        return result, data

    def ackCommand_setSimulationMode(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_setSimulationMode(cmdId, ackCode, errorCode, description)

    def subscribeCommand_setSimulationMode(self, action):
        self.commandSubscribers_setSimulationMode.append(action)
        if "command_setSimulationMode" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_setSimulationMode"] = [self.acceptCommand_setSimulationMode, self.commandSubscribers_setSimulationMode]

    def acceptCommand_setValue(self):
        data = SALPY_GenericCamera.GenericCamera_command_setValueC()
        result = self.sal.acceptCommand_setValue(data)
        return result, data

    def ackCommand_setValue(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_setValue(cmdId, ackCode, errorCode, description)

    def subscribeCommand_setValue(self, action):
        self.commandSubscribers_setValue.append(action)
        if "command_setValue" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_setValue"] = [self.acceptCommand_setValue, self.commandSubscribers_setValue]

    def acceptCommand_setROI(self):
        data = SALPY_GenericCamera.GenericCamera_command_setROIC()
        result = self.sal.acceptCommand_setROI(data)
        return result, data

    def ackCommand_setROI(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_setROI(cmdId, ackCode, errorCode, description)

    def subscribeCommand_setROI(self, action):
        self.commandSubscribers_setROI.append(action)
        if "command_setROI" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_setROI"] = [self.acceptCommand_setROI, self.commandSubscribers_setROI]

    def acceptCommand_setFullFrame(self):
        data = SALPY_GenericCamera.GenericCamera_command_setFullFrameC()
        result = self.sal.acceptCommand_setFullFrame(data)
        return result, data

    def ackCommand_setFullFrame(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_setFullFrame(cmdId, ackCode, errorCode, description)

    def subscribeCommand_setFullFrame(self, action):
        self.commandSubscribers_setFullFrame.append(action)
        if "command_setFullFrame" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_setFullFrame"] = [self.acceptCommand_setFullFrame, self.commandSubscribers_setFullFrame]

    def acceptCommand_startLiveView(self):
        data = SALPY_GenericCamera.GenericCamera_command_startLiveViewC()
        result = self.sal.acceptCommand_startLiveView(data)
        return result, data

    def ackCommand_startLiveView(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_startLiveView(cmdId, ackCode, errorCode, description)

    def subscribeCommand_startLiveView(self, action):
        self.commandSubscribers_startLiveView.append(action)
        if "command_startLiveView" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_startLiveView"] = [self.acceptCommand_startLiveView, self.commandSubscribers_startLiveView]

    def acceptCommand_stopLiveView(self):
        data = SALPY_GenericCamera.GenericCamera_command_stopLiveViewC()
        result = self.sal.acceptCommand_stopLiveView(data)
        return result, data

    def ackCommand_stopLiveView(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_stopLiveView(cmdId, ackCode, errorCode, description)

    def subscribeCommand_stopLiveView(self, action):
        self.commandSubscribers_stopLiveView.append(action)
        if "command_stopLiveView" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_stopLiveView"] = [self.acceptCommand_stopLiveView, self.commandSubscribers_stopLiveView]

    def acceptCommand_takeImages(self):
        data = SALPY_GenericCamera.GenericCamera_command_takeImagesC()
        result = self.sal.acceptCommand_takeImages(data)
        return result, data

    def ackCommand_takeImages(self, cmdId, ackCode, errorCode, description):
        return self.sal.ackCommand_takeImages(cmdId, ackCode, errorCode, description)

    def subscribeCommand_takeImages(self, action):
        self.commandSubscribers_takeImages.append(action)
        if "command_takeImages" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["command_takeImages"] = [self.acceptCommand_takeImages, self.commandSubscribers_takeImages]

    def logEvent_settingVersions(self, recommendedSettingsVersion, recommendedSettingsLabels, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_settingVersionsC()
        data.recommendedSettingsVersion = recommendedSettingsVersion
        data.recommendedSettingsLabels = recommendedSettingsLabels

        self.previousEvent_settingVersions = data
        return self.sal.logEvent_settingVersions(data, priority)

    def tryLogEvent_settingVersions(self, recommendedSettingsVersion, recommendedSettingsLabels, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_settingVersions.recommendedSettingsVersion != recommendedSettingsVersion
        anythingChanged = anythingChanged or self.previousEvent_settingVersions.recommendedSettingsLabels != recommendedSettingsLabels

        if anythingChanged:
            return self.logEvent_settingVersions(recommendedSettingsVersion, recommendedSettingsLabels, priority)
        return 0

    def logEvent_errorCode(self, errorCode, errorReport, traceback, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_errorCodeC()
        data.errorCode = errorCode
        data.errorReport = errorReport
        data.traceback = traceback

        self.previousEvent_errorCode = data
        return self.sal.logEvent_errorCode(data, priority)

    def tryLogEvent_errorCode(self, errorCode, errorReport, traceback, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_errorCode.errorCode != errorCode
        anythingChanged = anythingChanged or self.previousEvent_errorCode.errorReport != errorReport
        anythingChanged = anythingChanged or self.previousEvent_errorCode.traceback != traceback

        if anythingChanged:
            return self.logEvent_errorCode(errorCode, errorReport, traceback, priority)
        return 0

    def logEvent_summaryState(self, summaryState, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_summaryStateC()
        data.summaryState = summaryState

        self.previousEvent_summaryState = data
        return self.sal.logEvent_summaryState(data, priority)

    def tryLogEvent_summaryState(self, summaryState, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_summaryState.summaryState != summaryState

        if anythingChanged:
            return self.logEvent_summaryState(summaryState, priority)
        return 0

    def logEvent_appliedSettingsMatchStart(self, appliedSettingsMatchStartIsTrue, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_appliedSettingsMatchStartC()
        data.appliedSettingsMatchStartIsTrue = appliedSettingsMatchStartIsTrue

        self.previousEvent_appliedSettingsMatchStart = data
        return self.sal.logEvent_appliedSettingsMatchStart(data, priority)

    def tryLogEvent_appliedSettingsMatchStart(self, appliedSettingsMatchStartIsTrue, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_appliedSettingsMatchStart.appliedSettingsMatchStartIsTrue != appliedSettingsMatchStartIsTrue

        if anythingChanged:
            return self.logEvent_appliedSettingsMatchStart(appliedSettingsMatchStartIsTrue, priority)
        return 0

    def logEvent_logLevel(self, level, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_logLevelC()
        data.level = level

        self.previousEvent_logLevel = data
        return self.sal.logEvent_logLevel(data, priority)

    def tryLogEvent_logLevel(self, level, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_logLevel.level != level

        if anythingChanged:
            return self.logEvent_logLevel(level, priority)
        return 0

    def logEvent_logMessage(self, level, message, traceback, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_logMessageC()
        data.level = level
        data.message = message
        data.traceback = traceback

        self.previousEvent_logMessage = data
        return self.sal.logEvent_logMessage(data, priority)

    def tryLogEvent_logMessage(self, level, message, traceback, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_logMessage.level != level
        anythingChanged = anythingChanged or self.previousEvent_logMessage.message != message
        anythingChanged = anythingChanged or self.previousEvent_logMessage.traceback != traceback

        if anythingChanged:
            return self.logEvent_logMessage(level, message, traceback, priority)
        return 0

    def logEvent_simulationMode(self, mode, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_simulationModeC()
        data.mode = mode

        self.previousEvent_simulationMode = data
        return self.sal.logEvent_simulationMode(data, priority)

    def tryLogEvent_simulationMode(self, mode, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_simulationMode.mode != mode

        if anythingChanged:
            return self.logEvent_simulationMode(mode, priority)
        return 0

    def logEvent_heartbeat(self, heartbeat, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_heartbeatC()
        data.heartbeat = heartbeat

        self.previousEvent_heartbeat = data
        return self.sal.logEvent_heartbeat(data, priority)

    def tryLogEvent_heartbeat(self, heartbeat, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_heartbeat.heartbeat != heartbeat

        if anythingChanged:
            return self.logEvent_heartbeat(heartbeat, priority)
        return 0

    def logEvent_cameraInfo(self, cameraMakeAndModel, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_cameraInfoC()
        data.cameraMakeAndModel = cameraMakeAndModel

        self.previousEvent_cameraInfo = data
        return self.sal.logEvent_cameraInfo(data, priority)

    def tryLogEvent_cameraInfo(self, cameraMakeAndModel, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_cameraInfo.cameraMakeAndModel != cameraMakeAndModel

        if anythingChanged:
            return self.logEvent_cameraInfo(cameraMakeAndModel, priority)
        return 0

    def logEvent_cameraSpecificProperty(self, propertyName, propertyValue, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_cameraSpecificPropertyC()
        data.propertyName = propertyName
        data.propertyValue = propertyValue

        self.previousEvent_cameraSpecificProperty = data
        return self.sal.logEvent_cameraSpecificProperty(data, priority)

    def tryLogEvent_cameraSpecificProperty(self, propertyName, propertyValue, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_cameraSpecificProperty.propertyName != propertyName
        anythingChanged = anythingChanged or self.previousEvent_cameraSpecificProperty.propertyValue != propertyValue

        if anythingChanged:
            return self.logEvent_cameraSpecificProperty(propertyName, propertyValue, priority)
        return 0

    def logEvent_roi(self, topPixel, leftPixel, width, height, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_roiC()
        data.topPixel = topPixel
        data.leftPixel = leftPixel
        data.width = width
        data.height = height

        self.previousEvent_roi = data
        return self.sal.logEvent_roi(data, priority)

    def tryLogEvent_roi(self, topPixel, leftPixel, width, height, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_roi.topPixel != topPixel
        anythingChanged = anythingChanged or self.previousEvent_roi.leftPixel != leftPixel
        anythingChanged = anythingChanged or self.previousEvent_roi.width != width
        anythingChanged = anythingChanged or self.previousEvent_roi.height != height

        if anythingChanged:
            return self.logEvent_roi(topPixel, leftPixel, width, height, priority)
        return 0

    def logEvent_startLiveView(self, ip, port, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_startLiveViewC()
        data.ip = ip
        data.port = port

        self.previousEvent_startLiveView = data
        return self.sal.logEvent_startLiveView(data, priority)

    def tryLogEvent_startLiveView(self, ip, port, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_startLiveView.ip != ip
        anythingChanged = anythingChanged or self.previousEvent_startLiveView.port != port

        if anythingChanged:
            return self.logEvent_startLiveView(ip, port, priority)
        return 0

    def logEvent_endLiveView(self, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_endLiveViewC()

        self.previousEvent_endLiveView = data
        return self.sal.logEvent_endLiveView(data, priority)

    def tryLogEvent_endLiveView(self, priority=0):
        anythingChanged = False

        if anythingChanged:
            return self.logEvent_endLiveView(priority)
        return 0

    def logEvent_startTakeImage(self, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_startTakeImageC()

        self.previousEvent_startTakeImage = data
        return self.sal.logEvent_startTakeImage(data, priority)

    def tryLogEvent_startTakeImage(self, priority=0):
        anythingChanged = False

        if anythingChanged:
            return self.logEvent_startTakeImage(priority)
        return 0

    def logEvent_startShutterOpen(self, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_startShutterOpenC()

        self.previousEvent_startShutterOpen = data
        return self.sal.logEvent_startShutterOpen(data, priority)

    def tryLogEvent_startShutterOpen(self, priority=0):
        anythingChanged = False

        if anythingChanged:
            return self.logEvent_startShutterOpen(priority)
        return 0

    def logEvent_endShutterOpen(self, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_endShutterOpenC()

        self.previousEvent_endShutterOpen = data
        return self.sal.logEvent_endShutterOpen(data, priority)

    def tryLogEvent_endShutterOpen(self, priority=0):
        anythingChanged = False

        if anythingChanged:
            return self.logEvent_endShutterOpen(priority)
        return 0

    def logEvent_startIntegration(self, imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_startIntegrationC()
        data.imageSequenceName = imageSequenceName
        data.imagesInSequence = imagesInSequence
        data.imageName = imageName
        data.imageIndex = imageIndex
        data.timeStamp = timeStamp
        data.exposureTime = exposureTime

        self.previousEvent_startIntegration = data
        return self.sal.logEvent_startIntegration(data, priority)

    def tryLogEvent_startIntegration(self, imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_startIntegration.imageSequenceName != imageSequenceName
        anythingChanged = anythingChanged or self.previousEvent_startIntegration.imagesInSequence != imagesInSequence
        anythingChanged = anythingChanged or self.previousEvent_startIntegration.imageName != imageName
        anythingChanged = anythingChanged or self.previousEvent_startIntegration.imageIndex != imageIndex
        anythingChanged = anythingChanged or self.previousEvent_startIntegration.timeStamp != timeStamp
        anythingChanged = anythingChanged or self.previousEvent_startIntegration.exposureTime != exposureTime

        if anythingChanged:
            return self.logEvent_startIntegration(imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority)
        return 0

    def logEvent_endIntegration(self, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_endIntegrationC()

        self.previousEvent_endIntegration = data
        return self.sal.logEvent_endIntegration(data, priority)

    def tryLogEvent_endIntegration(self, priority=0):
        anythingChanged = False

        if anythingChanged:
            return self.logEvent_endIntegration(priority)
        return 0

    def logEvent_startShutterClose(self, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_startShutterCloseC()

        self.previousEvent_startShutterClose = data
        return self.sal.logEvent_startShutterClose(data, priority)

    def tryLogEvent_startShutterClose(self, priority=0):
        anythingChanged = False

        if anythingChanged:
            return self.logEvent_startShutterClose(priority)
        return 0

    def logEvent_endShutterClose(self, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_endShutterCloseC()

        self.previousEvent_endShutterClose = data
        return self.sal.logEvent_endShutterClose(data, priority)

    def tryLogEvent_endShutterClose(self, priority=0):
        anythingChanged = False

        if anythingChanged:
            return self.logEvent_endShutterClose(priority)
        return 0

    def logEvent_startReadout(self, imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_startReadoutC()
        data.imageSequenceName = imageSequenceName
        data.imagesInSequence = imagesInSequence
        data.imageName = imageName
        data.imageIndex = imageIndex
        data.timeStamp = timeStamp
        data.exposureTime = exposureTime

        self.previousEvent_startReadout = data
        return self.sal.logEvent_startReadout(data, priority)

    def tryLogEvent_startReadout(self, imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_startReadout.imageSequenceName != imageSequenceName
        anythingChanged = anythingChanged or self.previousEvent_startReadout.imagesInSequence != imagesInSequence
        anythingChanged = anythingChanged or self.previousEvent_startReadout.imageName != imageName
        anythingChanged = anythingChanged or self.previousEvent_startReadout.imageIndex != imageIndex
        anythingChanged = anythingChanged or self.previousEvent_startReadout.timeStamp != timeStamp
        anythingChanged = anythingChanged or self.previousEvent_startReadout.exposureTime != exposureTime

        if anythingChanged:
            return self.logEvent_startReadout(imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority)
        return 0

    def logEvent_endReadout(self, imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_endReadoutC()
        data.imageSequenceName = imageSequenceName
        data.imagesInSequence = imagesInSequence
        data.imageName = imageName
        data.imageIndex = imageIndex
        data.timeStamp = timeStamp
        data.exposureTime = exposureTime

        self.previousEvent_endReadout = data
        return self.sal.logEvent_endReadout(data, priority)

    def tryLogEvent_endReadout(self, imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority=0):
        anythingChanged = False
        anythingChanged = anythingChanged or self.previousEvent_endReadout.imageSequenceName != imageSequenceName
        anythingChanged = anythingChanged or self.previousEvent_endReadout.imagesInSequence != imagesInSequence
        anythingChanged = anythingChanged or self.previousEvent_endReadout.imageName != imageName
        anythingChanged = anythingChanged or self.previousEvent_endReadout.imageIndex != imageIndex
        anythingChanged = anythingChanged or self.previousEvent_endReadout.timeStamp != timeStamp
        anythingChanged = anythingChanged or self.previousEvent_endReadout.exposureTime != exposureTime

        if anythingChanged:
            return self.logEvent_endReadout(imageSequenceName, imagesInSequence, imageName, imageIndex, timeStamp, exposureTime, priority)
        return 0

    def logEvent_endTakeImage(self, priority=0):
        data = SALPY_GenericCamera.GenericCamera_logevent_endTakeImageC()

        self.previousEvent_endTakeImage = data
        return self.sal.logEvent_endTakeImage(data, priority)

    def tryLogEvent_endTakeImage(self, priority=0):
        anythingChanged = False

        if anythingChanged:
            return self.logEvent_endTakeImage(priority)
        return 0

    def putSample_temperature(self, temperature):
        data = SALPY_GenericCamera.GenericCamera_temperatureC()
        data.temperature = temperature

        return self.sal.putSample_temperature(data)


class GenericCameraRemote:
    def __init__(self, index=0):
        self.sal = SALPY_GenericCamera.SAL_GenericCamera(index)
        self.sal.setDebugLevel(0)
        self.sal.salCommand("GenericCamera_command_abort")
        self.sal.salCommand("GenericCamera_command_enable")
        self.sal.salCommand("GenericCamera_command_disable")
        self.sal.salCommand("GenericCamera_command_standby")
        self.sal.salCommand("GenericCamera_command_exitControl")
        self.sal.salCommand("GenericCamera_command_start")
        self.sal.salCommand("GenericCamera_command_enterControl")
        self.sal.salCommand("GenericCamera_command_setLogLevel")
        self.sal.salCommand("GenericCamera_command_setSimulationMode")
        self.sal.salCommand("GenericCamera_command_setValue")
        self.sal.salCommand("GenericCamera_command_setROI")
        self.sal.salCommand("GenericCamera_command_setFullFrame")
        self.sal.salCommand("GenericCamera_command_startLiveView")
        self.sal.salCommand("GenericCamera_command_stopLiveView")
        self.sal.salCommand("GenericCamera_command_takeImages")

        self.sal.salEvent("GenericCamera_logevent_settingVersions")
        self.sal.salEvent("GenericCamera_logevent_errorCode")
        self.sal.salEvent("GenericCamera_logevent_summaryState")
        self.sal.salEvent("GenericCamera_logevent_appliedSettingsMatchStart")
        self.sal.salEvent("GenericCamera_logevent_logLevel")
        self.sal.salEvent("GenericCamera_logevent_logMessage")
        self.sal.salEvent("GenericCamera_logevent_simulationMode")
        self.sal.salEvent("GenericCamera_logevent_heartbeat")
        self.sal.salEvent("GenericCamera_logevent_cameraInfo")
        self.sal.salEvent("GenericCamera_logevent_cameraSpecificProperty")
        self.sal.salEvent("GenericCamera_logevent_roi")
        self.sal.salEvent("GenericCamera_logevent_startLiveView")
        self.sal.salEvent("GenericCamera_logevent_endLiveView")
        self.sal.salEvent("GenericCamera_logevent_startTakeImage")
        self.sal.salEvent("GenericCamera_logevent_startShutterOpen")
        self.sal.salEvent("GenericCamera_logevent_endShutterOpen")
        self.sal.salEvent("GenericCamera_logevent_startIntegration")
        self.sal.salEvent("GenericCamera_logevent_endIntegration")
        self.sal.salEvent("GenericCamera_logevent_startShutterClose")
        self.sal.salEvent("GenericCamera_logevent_endShutterClose")
        self.sal.salEvent("GenericCamera_logevent_startReadout")
        self.sal.salEvent("GenericCamera_logevent_endReadout")
        self.sal.salEvent("GenericCamera_logevent_endTakeImage")

        self.sal.salTelemetrySub("GenericCamera_temperature")

        self.eventSubscribers_settingVersions = []
        self.eventSubscribers_errorCode = []
        self.eventSubscribers_summaryState = []
        self.eventSubscribers_appliedSettingsMatchStart = []
        self.eventSubscribers_logLevel = []
        self.eventSubscribers_logMessage = []
        self.eventSubscribers_simulationMode = []
        self.eventSubscribers_heartbeat = []
        self.eventSubscribers_cameraInfo = []
        self.eventSubscribers_cameraSpecificProperty = []
        self.eventSubscribers_roi = []
        self.eventSubscribers_startLiveView = []
        self.eventSubscribers_endLiveView = []
        self.eventSubscribers_startTakeImage = []
        self.eventSubscribers_startShutterOpen = []
        self.eventSubscribers_endShutterOpen = []
        self.eventSubscribers_startIntegration = []
        self.eventSubscribers_endIntegration = []
        self.eventSubscribers_startShutterClose = []
        self.eventSubscribers_endShutterClose = []
        self.eventSubscribers_startReadout = []
        self.eventSubscribers_endReadout = []
        self.eventSubscribers_endTakeImage = []

        self.telemetrySubscribers_temperature = []

        self.topicsSubscribedToo = {}

    def close(self):
        time.sleep(1)
        self.sal.salShutdown()

    def flush(self, action):
        result, data = action()
        while result >= 0:
            result, data = action()

    def checkForSubscriber(self, action, subscribers):
        buffer = []
        result, data = action()
        while result == 0:
            buffer.append(data)
            result, data = action()
        if len(buffer) > 0:
            for subscriber in subscribers:
                subscriber(buffer)

    def runSubscriberChecks(self):
        for subscribedTopic in self.topicsSubscribedToo:
            action = self.topicsSubscribedToo[subscribedTopic][0]
            subscribers = self.topicsSubscribedToo[subscribedTopic][1]
            self.checkForSubscriber(action, subscribers)

    def getEvent(self, action):
        lastResult, lastData = action()
        while lastResult >= 0:
            result, data = action()
            if result >= 0:
                lastResult = result
                lastData = data
            elif result < 0:
                break
        return lastResult, lastData

    def getTimestamp(self):
        return self.sal.getCurrentTime()

    def issueCommand_abort(self, value):
        data = SALPY_GenericCamera.GenericCamera_command_abortC()
        data.value = value

        return self.sal.issueCommand_abort(data)

    def getResponse_abort(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_abort(data)
        return result, data

    def waitForCompletion_abort(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_abort(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_abort()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_abort(self, value, timeoutInSeconds=10):
        cmdId = self.issueCommand_abort(value)
        return self.waitForCompletion_abort(cmdId, timeoutInSeconds)

    def issueCommand_enable(self, value):
        data = SALPY_GenericCamera.GenericCamera_command_enableC()
        data.value = value

        return self.sal.issueCommand_enable(data)

    def getResponse_enable(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_enable(data)
        return result, data

    def waitForCompletion_enable(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_enable(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_enable()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_enable(self, value, timeoutInSeconds=10):
        cmdId = self.issueCommand_enable(value)
        return self.waitForCompletion_enable(cmdId, timeoutInSeconds)

    def issueCommand_disable(self, value):
        data = SALPY_GenericCamera.GenericCamera_command_disableC()
        data.value = value

        return self.sal.issueCommand_disable(data)

    def getResponse_disable(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_disable(data)
        return result, data

    def waitForCompletion_disable(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_disable(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_disable()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_disable(self, value, timeoutInSeconds=10):
        cmdId = self.issueCommand_disable(value)
        return self.waitForCompletion_disable(cmdId, timeoutInSeconds)

    def issueCommand_standby(self, value):
        data = SALPY_GenericCamera.GenericCamera_command_standbyC()
        data.value = value

        return self.sal.issueCommand_standby(data)

    def getResponse_standby(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_standby(data)
        return result, data

    def waitForCompletion_standby(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_standby(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_standby()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_standby(self, value, timeoutInSeconds=10):
        cmdId = self.issueCommand_standby(value)
        return self.waitForCompletion_standby(cmdId, timeoutInSeconds)

    def issueCommand_exitControl(self, value):
        data = SALPY_GenericCamera.GenericCamera_command_exitControlC()
        data.value = value

        return self.sal.issueCommand_exitControl(data)

    def getResponse_exitControl(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_exitControl(data)
        return result, data

    def waitForCompletion_exitControl(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_exitControl(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_exitControl()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_exitControl(self, value, timeoutInSeconds=10):
        cmdId = self.issueCommand_exitControl(value)
        return self.waitForCompletion_exitControl(cmdId, timeoutInSeconds)

    def issueCommand_start(self, settingsToApply):
        data = SALPY_GenericCamera.GenericCamera_command_startC()
        data.settingsToApply = settingsToApply

        return self.sal.issueCommand_start(data)

    def getResponse_start(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_start(data)
        return result, data

    def waitForCompletion_start(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_start(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_start()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_start(self, settingsToApply, timeoutInSeconds=10):
        cmdId = self.issueCommand_start(settingsToApply)
        return self.waitForCompletion_start(cmdId, timeoutInSeconds)

    def issueCommand_enterControl(self, value):
        data = SALPY_GenericCamera.GenericCamera_command_enterControlC()
        data.value = value

        return self.sal.issueCommand_enterControl(data)

    def getResponse_enterControl(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_enterControl(data)
        return result, data

    def waitForCompletion_enterControl(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_enterControl(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_enterControl()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_enterControl(self, value, timeoutInSeconds=10):
        cmdId = self.issueCommand_enterControl(value)
        return self.waitForCompletion_enterControl(cmdId, timeoutInSeconds)

    def issueCommand_setLogLevel(self, level):
        data = SALPY_GenericCamera.GenericCamera_command_setLogLevelC()
        data.level = level

        return self.sal.issueCommand_setLogLevel(data)

    def getResponse_setLogLevel(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_setLogLevel(data)
        return result, data

    def waitForCompletion_setLogLevel(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_setLogLevel(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_setLogLevel()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_setLogLevel(self, level, timeoutInSeconds=10):
        cmdId = self.issueCommand_setLogLevel(level)
        return self.waitForCompletion_setLogLevel(cmdId, timeoutInSeconds)

    def issueCommand_setSimulationMode(self, mode):
        data = SALPY_GenericCamera.GenericCamera_command_setSimulationModeC()
        data.mode = mode

        return self.sal.issueCommand_setSimulationMode(data)

    def getResponse_setSimulationMode(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_setSimulationMode(data)
        return result, data

    def waitForCompletion_setSimulationMode(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_setSimulationMode(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_setSimulationMode()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_setSimulationMode(self, mode, timeoutInSeconds=10):
        cmdId = self.issueCommand_setSimulationMode(mode)
        return self.waitForCompletion_setSimulationMode(cmdId, timeoutInSeconds)

    def issueCommand_setValue(self, parametersAndValues):
        data = SALPY_GenericCamera.GenericCamera_command_setValueC()
        data.parametersAndValues = parametersAndValues

        return self.sal.issueCommand_setValue(data)

    def getResponse_setValue(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_setValue(data)
        return result, data

    def waitForCompletion_setValue(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_setValue(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_setValue()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_setValue(self, parametersAndValues, timeoutInSeconds=10):
        cmdId = self.issueCommand_setValue(parametersAndValues)
        return self.waitForCompletion_setValue(cmdId, timeoutInSeconds)

    def issueCommand_setROI(self, topPixel, leftPixel, width, height):
        data = SALPY_GenericCamera.GenericCamera_command_setROIC()
        data.topPixel = topPixel
        data.leftPixel = leftPixel
        data.width = width
        data.height = height

        return self.sal.issueCommand_setROI(data)

    def getResponse_setROI(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_setROI(data)
        return result, data

    def waitForCompletion_setROI(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_setROI(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_setROI()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_setROI(self, topPixel, leftPixel, width, height, timeoutInSeconds=10):
        cmdId = self.issueCommand_setROI(topPixel, leftPixel, width, height)
        return self.waitForCompletion_setROI(cmdId, timeoutInSeconds)

    def issueCommand_setFullFrame(self, ignored):
        data = SALPY_GenericCamera.GenericCamera_command_setFullFrameC()
        data.ignored = ignored

        return self.sal.issueCommand_setFullFrame(data)

    def getResponse_setFullFrame(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_setFullFrame(data)
        return result, data

    def waitForCompletion_setFullFrame(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_setFullFrame(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_setFullFrame()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_setFullFrame(self, ignored, timeoutInSeconds=10):
        cmdId = self.issueCommand_setFullFrame(ignored)
        return self.waitForCompletion_setFullFrame(cmdId, timeoutInSeconds)

    def issueCommand_startLiveView(self, expTime):
        data = SALPY_GenericCamera.GenericCamera_command_startLiveViewC()
        data.expTime = expTime

        return self.sal.issueCommand_startLiveView(data)

    def getResponse_startLiveView(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_startLiveView(data)
        return result, data

    def waitForCompletion_startLiveView(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_startLiveView(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_startLiveView()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_startLiveView(self, expTime, timeoutInSeconds=10):
        cmdId = self.issueCommand_startLiveView(expTime)
        return self.waitForCompletion_startLiveView(cmdId, timeoutInSeconds)

    def issueCommand_stopLiveView(self, ignored):
        data = SALPY_GenericCamera.GenericCamera_command_stopLiveViewC()
        data.ignored = ignored

        return self.sal.issueCommand_stopLiveView(data)

    def getResponse_stopLiveView(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_stopLiveView(data)
        return result, data

    def waitForCompletion_stopLiveView(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_stopLiveView(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_stopLiveView()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_stopLiveView(self, ignored, timeoutInSeconds=10):
        cmdId = self.issueCommand_stopLiveView(ignored)
        return self.waitForCompletion_stopLiveView(cmdId, timeoutInSeconds)

    def issueCommand_takeImages(self, numImages, expTime, shutter, imageSequenceName):
        data = SALPY_GenericCamera.GenericCamera_command_takeImagesC()
        data.numImages = numImages
        data.expTime = expTime
        data.shutter = shutter
        data.imageSequenceName = imageSequenceName

        return self.sal.issueCommand_takeImages(data)

    def getResponse_takeImages(self):
        data = SALPY_GenericCamera.GenericCamera_ackcmdC()
        result = self.sal.getResponse_takeImages(data)
        return result, data

    def waitForCompletion_takeImages(self, cmdId, timeoutInSeconds=10):
        waitResult = self.sal.waitForCompletion_takeImages(cmdId, timeoutInSeconds)
        #ackResult, ack = self.getResponse_takeImages()
        #return waitResult, ackResult, ack
        return waitResult

    def issueCommandThenWait_takeImages(self, numImages, expTime, shutter, imageSequenceName, timeoutInSeconds=10):
        cmdId = self.issueCommand_takeImages(numImages, expTime, shutter, imageSequenceName)
        return self.waitForCompletion_takeImages(cmdId, timeoutInSeconds)

    def getNextEvent_settingVersions(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_settingVersionsC()
        result = self.sal.getEvent_settingVersions(data)
        return result, data
        
    def getEvent_settingVersions(self):
        return self.getEvent(self.getNextEvent_settingVersions)
        
    def subscribeEvent_settingVersions(self, action):
        self.eventSubscribers_settingVersions.append(action)
        if "event_settingVersions" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_settingVersions"] = [self.getNextEvent_settingVersions, self.eventSubscribers_settingVersions]

    def getNextEvent_errorCode(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_errorCodeC()
        result = self.sal.getEvent_errorCode(data)
        return result, data
        
    def getEvent_errorCode(self):
        return self.getEvent(self.getNextEvent_errorCode)
        
    def subscribeEvent_errorCode(self, action):
        self.eventSubscribers_errorCode.append(action)
        if "event_errorCode" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_errorCode"] = [self.getNextEvent_errorCode, self.eventSubscribers_errorCode]

    def getNextEvent_summaryState(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_summaryStateC()
        result = self.sal.getEvent_summaryState(data)
        return result, data
        
    def getEvent_summaryState(self):
        return self.getEvent(self.getNextEvent_summaryState)
        
    def subscribeEvent_summaryState(self, action):
        self.eventSubscribers_summaryState.append(action)
        if "event_summaryState" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_summaryState"] = [self.getNextEvent_summaryState, self.eventSubscribers_summaryState]

    def getNextEvent_appliedSettingsMatchStart(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_appliedSettingsMatchStartC()
        result = self.sal.getEvent_appliedSettingsMatchStart(data)
        return result, data
        
    def getEvent_appliedSettingsMatchStart(self):
        return self.getEvent(self.getNextEvent_appliedSettingsMatchStart)
        
    def subscribeEvent_appliedSettingsMatchStart(self, action):
        self.eventSubscribers_appliedSettingsMatchStart.append(action)
        if "event_appliedSettingsMatchStart" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_appliedSettingsMatchStart"] = [self.getNextEvent_appliedSettingsMatchStart, self.eventSubscribers_appliedSettingsMatchStart]

    def getNextEvent_logLevel(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_logLevelC()
        result = self.sal.getEvent_logLevel(data)
        return result, data
        
    def getEvent_logLevel(self):
        return self.getEvent(self.getNextEvent_logLevel)
        
    def subscribeEvent_logLevel(self, action):
        self.eventSubscribers_logLevel.append(action)
        if "event_logLevel" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_logLevel"] = [self.getNextEvent_logLevel, self.eventSubscribers_logLevel]

    def getNextEvent_logMessage(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_logMessageC()
        result = self.sal.getEvent_logMessage(data)
        return result, data
        
    def getEvent_logMessage(self):
        return self.getEvent(self.getNextEvent_logMessage)
        
    def subscribeEvent_logMessage(self, action):
        self.eventSubscribers_logMessage.append(action)
        if "event_logMessage" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_logMessage"] = [self.getNextEvent_logMessage, self.eventSubscribers_logMessage]

    def getNextEvent_simulationMode(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_simulationModeC()
        result = self.sal.getEvent_simulationMode(data)
        return result, data
        
    def getEvent_simulationMode(self):
        return self.getEvent(self.getNextEvent_simulationMode)
        
    def subscribeEvent_simulationMode(self, action):
        self.eventSubscribers_simulationMode.append(action)
        if "event_simulationMode" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_simulationMode"] = [self.getNextEvent_simulationMode, self.eventSubscribers_simulationMode]

    def getNextEvent_heartbeat(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_heartbeatC()
        result = self.sal.getEvent_heartbeat(data)
        return result, data
        
    def getEvent_heartbeat(self):
        return self.getEvent(self.getNextEvent_heartbeat)
        
    def subscribeEvent_heartbeat(self, action):
        self.eventSubscribers_heartbeat.append(action)
        if "event_heartbeat" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_heartbeat"] = [self.getNextEvent_heartbeat, self.eventSubscribers_heartbeat]

    def getNextEvent_cameraInfo(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_cameraInfoC()
        result = self.sal.getEvent_cameraInfo(data)
        return result, data
        
    def getEvent_cameraInfo(self):
        return self.getEvent(self.getNextEvent_cameraInfo)
        
    def subscribeEvent_cameraInfo(self, action):
        self.eventSubscribers_cameraInfo.append(action)
        if "event_cameraInfo" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_cameraInfo"] = [self.getNextEvent_cameraInfo, self.eventSubscribers_cameraInfo]

    def getNextEvent_cameraSpecificProperty(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_cameraSpecificPropertyC()
        result = self.sal.getEvent_cameraSpecificProperty(data)
        return result, data
        
    def getEvent_cameraSpecificProperty(self):
        return self.getEvent(self.getNextEvent_cameraSpecificProperty)
        
    def subscribeEvent_cameraSpecificProperty(self, action):
        self.eventSubscribers_cameraSpecificProperty.append(action)
        if "event_cameraSpecificProperty" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_cameraSpecificProperty"] = [self.getNextEvent_cameraSpecificProperty, self.eventSubscribers_cameraSpecificProperty]

    def getNextEvent_roi(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_roiC()
        result = self.sal.getEvent_roi(data)
        return result, data
        
    def getEvent_roi(self):
        return self.getEvent(self.getNextEvent_roi)
        
    def subscribeEvent_roi(self, action):
        self.eventSubscribers_roi.append(action)
        if "event_roi" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_roi"] = [self.getNextEvent_roi, self.eventSubscribers_roi]

    def getNextEvent_startLiveView(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_startLiveViewC()
        result = self.sal.getEvent_startLiveView(data)
        return result, data
        
    def getEvent_startLiveView(self):
        return self.getEvent(self.getNextEvent_startLiveView)
        
    def subscribeEvent_startLiveView(self, action):
        self.eventSubscribers_startLiveView.append(action)
        if "event_startLiveView" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_startLiveView"] = [self.getNextEvent_startLiveView, self.eventSubscribers_startLiveView]

    def getNextEvent_endLiveView(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_endLiveViewC()
        result = self.sal.getEvent_endLiveView(data)
        return result, data
        
    def getEvent_endLiveView(self):
        return self.getEvent(self.getNextEvent_endLiveView)
        
    def subscribeEvent_endLiveView(self, action):
        self.eventSubscribers_endLiveView.append(action)
        if "event_endLiveView" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_endLiveView"] = [self.getNextEvent_endLiveView, self.eventSubscribers_endLiveView]

    def getNextEvent_startTakeImage(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_startTakeImageC()
        result = self.sal.getEvent_startTakeImage(data)
        return result, data
        
    def getEvent_startTakeImage(self):
        return self.getEvent(self.getNextEvent_startTakeImage)
        
    def subscribeEvent_startTakeImage(self, action):
        self.eventSubscribers_startTakeImage.append(action)
        if "event_startTakeImage" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_startTakeImage"] = [self.getNextEvent_startTakeImage, self.eventSubscribers_startTakeImage]

    def getNextEvent_startShutterOpen(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_startShutterOpenC()
        result = self.sal.getEvent_startShutterOpen(data)
        return result, data
        
    def getEvent_startShutterOpen(self):
        return self.getEvent(self.getNextEvent_startShutterOpen)
        
    def subscribeEvent_startShutterOpen(self, action):
        self.eventSubscribers_startShutterOpen.append(action)
        if "event_startShutterOpen" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_startShutterOpen"] = [self.getNextEvent_startShutterOpen, self.eventSubscribers_startShutterOpen]

    def getNextEvent_endShutterOpen(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_endShutterOpenC()
        result = self.sal.getEvent_endShutterOpen(data)
        return result, data
        
    def getEvent_endShutterOpen(self):
        return self.getEvent(self.getNextEvent_endShutterOpen)
        
    def subscribeEvent_endShutterOpen(self, action):
        self.eventSubscribers_endShutterOpen.append(action)
        if "event_endShutterOpen" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_endShutterOpen"] = [self.getNextEvent_endShutterOpen, self.eventSubscribers_endShutterOpen]

    def getNextEvent_startIntegration(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_startIntegrationC()
        result = self.sal.getEvent_startIntegration(data)
        return result, data
        
    def getEvent_startIntegration(self):
        return self.getEvent(self.getNextEvent_startIntegration)
        
    def subscribeEvent_startIntegration(self, action):
        self.eventSubscribers_startIntegration.append(action)
        if "event_startIntegration" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_startIntegration"] = [self.getNextEvent_startIntegration, self.eventSubscribers_startIntegration]

    def getNextEvent_endIntegration(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_endIntegrationC()
        result = self.sal.getEvent_endIntegration(data)
        return result, data
        
    def getEvent_endIntegration(self):
        return self.getEvent(self.getNextEvent_endIntegration)
        
    def subscribeEvent_endIntegration(self, action):
        self.eventSubscribers_endIntegration.append(action)
        if "event_endIntegration" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_endIntegration"] = [self.getNextEvent_endIntegration, self.eventSubscribers_endIntegration]

    def getNextEvent_startShutterClose(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_startShutterCloseC()
        result = self.sal.getEvent_startShutterClose(data)
        return result, data
        
    def getEvent_startShutterClose(self):
        return self.getEvent(self.getNextEvent_startShutterClose)
        
    def subscribeEvent_startShutterClose(self, action):
        self.eventSubscribers_startShutterClose.append(action)
        if "event_startShutterClose" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_startShutterClose"] = [self.getNextEvent_startShutterClose, self.eventSubscribers_startShutterClose]

    def getNextEvent_endShutterClose(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_endShutterCloseC()
        result = self.sal.getEvent_endShutterClose(data)
        return result, data
        
    def getEvent_endShutterClose(self):
        return self.getEvent(self.getNextEvent_endShutterClose)
        
    def subscribeEvent_endShutterClose(self, action):
        self.eventSubscribers_endShutterClose.append(action)
        if "event_endShutterClose" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_endShutterClose"] = [self.getNextEvent_endShutterClose, self.eventSubscribers_endShutterClose]

    def getNextEvent_startReadout(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_startReadoutC()
        result = self.sal.getEvent_startReadout(data)
        return result, data
        
    def getEvent_startReadout(self):
        return self.getEvent(self.getNextEvent_startReadout)
        
    def subscribeEvent_startReadout(self, action):
        self.eventSubscribers_startReadout.append(action)
        if "event_startReadout" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_startReadout"] = [self.getNextEvent_startReadout, self.eventSubscribers_startReadout]

    def getNextEvent_endReadout(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_endReadoutC()
        result = self.sal.getEvent_endReadout(data)
        return result, data
        
    def getEvent_endReadout(self):
        return self.getEvent(self.getNextEvent_endReadout)
        
    def subscribeEvent_endReadout(self, action):
        self.eventSubscribers_endReadout.append(action)
        if "event_endReadout" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_endReadout"] = [self.getNextEvent_endReadout, self.eventSubscribers_endReadout]

    def getNextEvent_endTakeImage(self):
        data = SALPY_GenericCamera.GenericCamera_logevent_endTakeImageC()
        result = self.sal.getEvent_endTakeImage(data)
        return result, data
        
    def getEvent_endTakeImage(self):
        return self.getEvent(self.getNextEvent_endTakeImage)
        
    def subscribeEvent_endTakeImage(self, action):
        self.eventSubscribers_endTakeImage.append(action)
        if "event_endTakeImage" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["event_endTakeImage"] = [self.getNextEvent_endTakeImage, self.eventSubscribers_endTakeImage]

    def getNextSample_temperature(self):
        data = SALPY_GenericCamera.GenericCamera_temperatureC()
        result = self.sal.getNextSample_temperature(data)
        return result, data

    def getSample_temperature(self):
        data = SALPY_GenericCamera.GenericCamera_temperatureC()
        result = self.sal.getSample_temperature(data)
        return result, data
        
    def subscribeTelemetry_temperature(self, action):
        self.telemetrySubscribers_temperature.append(action)
        if "telemetry_temperature" not in self.topicsSubscribedToo:
            self.topicsSubscribedToo["telemetry_temperature"] = [self.getNextSample_temperature, self.telemetrySubscribers_temperature]


class SummaryStates:
    OfflineState = SALPY_GenericCamera.SAL__STATE_OFFLINE
    StandbyState = SALPY_GenericCamera.SAL__STATE_STANDBY
    DisabledState = SALPY_GenericCamera.SAL__STATE_DISABLED
    EnabledState = SALPY_GenericCamera.SAL__STATE_ENABLED
    FaultState = SALPY_GenericCamera.SAL__STATE_FAULT
