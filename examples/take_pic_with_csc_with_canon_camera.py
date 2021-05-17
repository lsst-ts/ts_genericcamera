import argparse
import asyncio
import logging

from lsst.ts import salobj

logging.basicConfig(
    format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",
    level=logging.INFO,
)

parser = argparse.ArgumentParser(
    description="Command the GenericCamera CSC to take pictures."
)
parser.add_argument("--index", default=1, type=int, help="CSC index (default: 1)")
args = parser.parse_args()


async def main():
    logging.info("main method")
    async with salobj.Domain() as domain:
        remote = salobj.Remote(domain=domain, name="GenericCamera", index=args.index)
        logging.info(f"starting remote with index {args.index}")
        await remote.start_task
        logging.info("starting CSC")
        await remote.cmd_start.set_start(timeout=120)
        logging.info("disabling")
        await salobj.set_summary_state(
            remote=remote, state=salobj.State.DISABLED, timeout=120
        )
        logging.info("enabling")
        await salobj.set_summary_state(
            remote=remote, state=salobj.State.ENABLED, timeout=120
        )
        logging.info("taking a picture")
        await remote.cmd_takeImages.set_start(
            numImages=1,
            expTime=2.0,
            shutter=True,
            sensors="",
            keyValueMap="",
            obsNote="image",
        )
        logging.info("disabling again")
        await salobj.set_summary_state(
            remote=remote, state=salobj.State.DISABLED, timeout=120
        )
        logging.info("offline")
        await salobj.set_summary_state(
            remote=remote, state=salobj.State.OFFLINE, timeout=120
        )


if __name__ == "__main__":
    logging.info("main")
    try:
        logging.info("Calling main method")
        asyncio.run(main())
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
