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

__all__ = ["CONFIG_SCHEMA"]

import yaml

CONFIG_SCHEMA = yaml.safe_load(
    """
    $schema: http://json-schema.org/draft-07/schema#
    $id: https://github.com/lsst-ts/ts_GenericCamera/blob/master/python/lsst/ts/GenericCamera/config_schema.py
    # title must end with one or more spaces followed by the schema version, which must begin with "v"
    title: GenericCamera v1
    description: Schema for GenericCamera configuration files
    type: object
    properties:
      ip:
        description: IP address of the live view server.
        type: string
        default: 127.0.0.1
      port:
        description: Port for the live view server.
        type: number
        default: 5013
      directory:
        description: Directory to store images (default is home folder).
        type: string
        default: ~/
      fileNameFormat:
        description: File name format.
        type: string
        default: "{timestamp}-{index}-{total}"
      camera:
        description: Camera driver to use.
        type: string
        enum:
        - Simulator
        - Andor
        - Zwo
        - Canon
        default: Simulator
    allOf:
    # For each supported camera add a new if/then case below.
    # Warning: set the default values for each case at the camera level
    # (rather than deeper down on properties within camera),
    # so users can omit camera and still get proper defaults.
    - if:
        properties:
          camera:
            const: Simulator
      then:
        properties:
          maxWidth:
            type: number
            default: 1024
            minimum: 1024
            maximum: 2048
          maxHeight:
            type: number
            default: 1024
            minimum: 1024
            maximum: 2048
    - if:
        properties:
          camera:
            const: Andor
      then:
        properties:
          id:
            default: 0
            type: number
          accumulateCount:
            default: 1
            type: number
          binValue:
            default: 1
            type: number
          ImageType:
            default: Mono16
            type: string
            enum:
              - Mono12
              - Mono12Packed
              - Mono16
              - Mono32
    - if:
        properties:
          camera:
            const: Zwo
      then:
        properties:
          id:
            default: 0
            type: number
          binValue:
            default: 1
            type: number
          currentImageType:
            default: Raw16
            type: string
            enum:
              - Raw8
              - RGB24
              - Raw16
              - Y8
          useZWOFilterWheel:
            default: true
            type: boolean
          filterId:
            default: 1
            type: number
          filterNumber:
            default: 2
            type: number
    - if:
        properties:
          camera:
            const: Canon
      then:
        properties:
          id:
            default: 0
            type: number
          binValue:
            default: 1
            type: number
          width:
            type: number
            default: 6744
          height:
            type: number
            default: 4502
          iso:
            type: number
            default: 200
          ImageType:
            default: RAW
            type: string
            enum:
              - RAW
    """
)
