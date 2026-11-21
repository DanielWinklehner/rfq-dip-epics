"""python -m mist2sim --config file.yaml"""

import argparse
import asyncio
import logging
import os
import sys

from .core import ConfigError, build, load_config, serve


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m mist2sim", description=__doc__)
    parser.add_argument("--config", required=True, help="YAML file with the list of simulators")
    parser.add_argument("--host", default="0.0.0.0", help="address to listen on (default: all)")
    parser.add_argument("--ready-file", help="file that exists while every simulator listens "
                                             "(for a health check)")
    args = parser.parse_args(argv)
    if args.ready_file and os.path.exists(args.ready_file):
        os.unlink(args.ready_file)      # left by a process that was killed
    logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        sims = [build(entry) for entry in load_config(args.config)]
    except ConfigError as exc:
        print("configuration error: %s" % exc, file=sys.stderr)
        return 2
    try:
        asyncio.run(serve(sims, args.host, ready_file=args.ready_file))
    except OSError as exc:
        print("cannot start: %s" % exc, file=sys.stderr)
        return 1
    logging.getLogger("mist2sim").info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
