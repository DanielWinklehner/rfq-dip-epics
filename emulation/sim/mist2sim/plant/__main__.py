"""python -m mist2sim.plant --config config/plant.yaml"""

import argparse
import asyncio
import logging
import signal
import sys

from .process import Plant, PlantConfigError, load_plant_config


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m mist2sim.plant", description=__doc__)
    parser.add_argument("--config", required=True, help="plant configuration (YAML)")
    args = parser.parse_args(argv)
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        plant = Plant(load_plant_config(args.config))
    except PlantConfigError as exc:
        print("configuration error: %s" % exc, file=sys.stderr)
        return 2

    async def run():
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, stop.set)
        await plant.run(stop)

    try:
        asyncio.run(run())
    except OSError as exc:
        print("cannot start: %s" % exc, file=sys.stderr)
        return 1
    logging.getLogger("mist2sim.plant").info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
