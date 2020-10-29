#!/usr/bin/env python
import asyncio

from lsst.ts.GenericCamera import GenericCameraCsc

asyncio.run(GenericCameraCsc.amain(index=None))
