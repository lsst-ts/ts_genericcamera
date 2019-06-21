#!/usr/bin/env python
import asyncio
import argparse

from lsst.ts.GenericCamera import GenericCameraCsc, version

parser = argparse.ArgumentParser(f"Start the GenericCamera CSC")
parser.add_argument("--version", action="version", version=version.__version__)
parser.add_argument("-v", "--verbose", dest="verbose", action='count', default=0,
                    help="Set the verbosity for console logging.")
parser.add_argument("-i", "--index", type=int, default=1,
                    help="SAL index; use the default value unless you sure you know what you are doing")

args = parser.parse_args()

csc = GenericCameraCsc(index=args.index)

asyncio.get_event_loop().run_until_complete(csc.done_task)
