"""python -m mist2loop --config <file>: run the control loops of the configuration.

Ends cleanly on SIGTERM or SIGINT, with every loop in MANUAL."""
import argparse
import logging
import signal
import sys

import yaml


def main(argv=None):
    parser = argparse.ArgumentParser(prog="mist2loop", description=__doc__)
    parser.add_argument("--config", required=True, help="YAML file: period_s, loops")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    with open(args.config, encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    from .service import Service              # imports pyepics: after the arguments are read

    service = Service(config)
    signal.signal(signal.SIGTERM, lambda *a: service.stopping.set())
    signal.signal(signal.SIGINT, lambda *a: service.stopping.set())
    service.run()


if __name__ == "__main__":
    main()
