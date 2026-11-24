"""python -m mist2scan run|check <definition.yaml> [overrides]

  run    the scan: files in <output>/<name>-<date>-<time>/ (points.csv, scan.json,
         definition.yaml). ctrl-c or SIGTERM end it cleanly (the actuator goes to the end value)
  check  connect, read, print what the scan would do (points, limits, estimated time) and
         whether it would start; writes nothing, neither to a PV nor to a file

Exit codes: 0 completed (check: it would start), 2 definition or command line error, 3 refused,
4 a condition lost, 5 the actuator lost, 6 a required detector lost, 7 a point not settled
(on_not_settled: end), 8 program error, 130 ctrl-c, 143 SIGTERM. docs/emulation/SCAN.md.
"""
import argparse
import logging
import signal
import sys

from . import VERSION, engine
from .definition import DefinitionError, load


def parser():
    p = argparse.ArgumentParser(prog="mist2scan", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version="mist2scan " + VERSION)
    sub = p.add_subparsers(dest="command")
    sub.required = True
    for name, text in (("run", "run the scan"), ("check", "print the plan, write nothing")):
        s = sub.add_parser(name, help=text)
        s.add_argument("definition", help="the definition file (YAML)")
        s.add_argument("--start", type=float, help="first point (replaces points)")
        s.add_argument("--stop", type=float, help="last point (replaces points)")
        s.add_argument("--step", type=float, help="step (replaces points)")
        s.add_argument("--dwell", type=float, help="seconds per point to collect the detectors")
        s.add_argument("--output", help="directory for the scan's directory")
        s.add_argument("-v", "--verbose", action="store_true", help="log every write")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        d = load(args.definition, start=args.start, stop=args.stop, step=args.step,
                 dwell=args.dwell, output=args.output)
    except (DefinitionError, OSError) as exc:
        print("mist2scan: %s" % exc, file=sys.stderr)
        return engine.DEFINITION

    from .ca import Channels                  # imports pyepics: after the definition is read
    from .files import ScanFiles

    io = Channels(writable=d.set_pv)
    scan = engine.Scan(d, io)
    try:
        if args.command == "check":
            return check(scan)
        signal.signal(signal.SIGINT, lambda signum, frame: scan.request_stop(signum))
        signal.signal(signal.SIGTERM, lambda signum, frame: scan.request_stop(signum))
        try:
            return scan.run(lambda name, t: ScanFiles(d.output, name, t),
                            command=[sys.executable, "-m", "mist2scan"] + list(
                                sys.argv[1:] if argv is None else argv))
        except engine.Refused as exc:
            print("mist2scan: refused, nothing written:", file=sys.stderr)
            for r in exc.reasons:
                print("  - %s" % r, file=sys.stderr)
            return engine.REFUSED
        except Exception:                   # before the first point: nothing was written
            logging.exception("mist2scan: error before the scan started")
            return engine.ERROR
    finally:
        io.close()


def check(scan):
    d = scan.d
    try:
        plan = scan.prepare()
        refused = []
    except engine.Refused as exc:
        plan, refused = exc.plan, exc.reasons
    lim = plan["limits"]
    pts = plan["points"]
    print("definition   %s%s" % (d.source, " (%s)" % d.name if d.name else ""))
    print("actuator     set %s, read-back %s, tolerance %g, settle timeout %g s, settle time "
          "%g s" % (d.set_pv, d.readback_pv, d.tolerance, d.settle_timeout, d.settle_time))
    print("part steps   %s" % ("none" if d.max_step is None else "at most %g, %g s apart"
                               % (d.max_step, d.step_pause)))
    print("limits       definition [%g, %g], set PV control limits %s, used [%g, %g]"
          % (tuple(lim["definition"]) + (("[%g, %g]" % tuple(lim["control"]))
                                         if lim["control"] else "none",)
             + tuple(lim["effective"])))
    b = plan["before"]
    print("now          set %s, read-back %s" % (b["set"], b["readback"]))
    print("points       %d: %s" % (len(pts), _points(pts)))
    print("detectors    %s" % ", ".join("%s (%s, %s)" % (x.name, x.pv, "required" if x.required
                                                          else "optional") for x in d.detectors))
    print("dwell        %g s per point" % d.dwell)
    print("conditions   %s" % (", ".join(c.text() for c in d.conditions) or "none"))
    print("at the end   %s%s" % (d.end, "" if plan["end_target"] is None
                                 or d.end != "previous" else " (%g)" % plan["end_target"]))
    print("not settled  %s" % d.on_not_settled)
    for n, i in plan["pvs"].items():
        print("pv           %-32s %s" % (n, "NOT CONNECTED" if not i["connected"] else
                                         "units %r" % i.get("units")))
    e = plan["estimate_s"]
    print("time         %.0f s plus settling, at most %.0f s (every point to its settle timeout)"
          % (e[0], e[1]))
    print("output       %s" % d.output)
    for w in plan["warnings"]:
        print("warning      %s" % w)
    if refused:
        print("WOULD BE REFUSED:")
        for r in refused:
            print("  - %s" % r)
        return engine.REFUSED
    print("it would start")
    return 0


def _points(pts):
    if len(pts) <= 8:
        return ", ".join("%g" % x for x in pts)
    return "%s ... %s" % (", ".join("%g" % x for x in pts[:4]),
                          ", ".join("%g" % x for x in pts[-3:]))


if __name__ == "__main__":
    sys.exit(main())
