import asyncio
from lsst.ts import salobj


async def main():
    print("main method")
    async with salobj.Domain() as domain:
        remote = salobj.Remote(domain=domain, name="GenericCamera", index=10)
        await remote.start_task
        await remote.cmd_start.set_start(timeout=20)
        print("disabling")
        await salobj.set_summary_state(remote=remote, state=salobj.State.DISABLED)
        print("enabling")
        await salobj.set_summary_state(remote=remote, state=salobj.State.ENABLED)
        print("taking a picture")
        await remote.cmd_takeImages.set_start(
            numImages=1,
            expTime=2.0,
            shutter=False,
            science=False,
            guide=False,
            wfs=False,
            imageSequenceName="image",
        )
        print("disabling again")
        await salobj.set_summary_state(remote=remote, state=salobj.State.DISABLED)
        print("offline")
        await salobj.set_summary_state(remote=remote, state=salobj.State.OFFLINE)


if __name__ == "__main__":
    print("main")
    loop = asyncio.get_event_loop()
    try:
        print("Calling main method")
        loop.run_until_complete(main())
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
