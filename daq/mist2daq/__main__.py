"""python -m mist2daq --config <file.yaml> [--check]"""

import argparse
import logging
import sys

from .backends import BackendError, make_backend
from .config import ConfigError, load
from .service import serve


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mist2daq", description=__doc__)
    parser.add_argument("--config", required=True, help="configuration file (YAML)")
    parser.add_argument("--check", action="store_true",
                        help="check the configuration and open the backend, then exit (writes nothing)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = load(args.config)
        backend = make_backend(config)
        if args.check:
            backend.open()
            backend.close()
            print("%s: configuration OK, backend %s opened and closed" % (args.config, config.backend["type"]))
            return 0
        serve(config, backend)
    except (ConfigError, BackendError, OSError) as exc:
        logging.getLogger("mist2daq").error("%s", exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
