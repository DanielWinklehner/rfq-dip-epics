"""Write the Grafana dashboards from the registry: one per page of the GUI, with the GUI's groups.

    python3 logger/mist2log/dashboards.py REGISTRY OUT_DIR      (make -C logger up does this)

Standard library only. The pages and their trends follow the GUI (RAS/mist2/ReactApp/src):
the Overview (every installed device), one page per subsystem page of the registry, Trends (any
logged PV, picked) and Infrastructure. A subsystem page trends the read-backs of its devices
whose roles the registry lists under trends.roles (their connected channels too), one graph per
role and unit as the GUI's TrendSet, on a log scale for pressures, with the set point of
trends.beside in the graph of its read-back (the loop: measured value with set point, output in
a graph of its own). Every page has the event log of its devices. No dashboard is edited by
hand: Grafana loads these files read-only.
"""
import json
import os
import re
import sys

# Words of the trend roles, as roles.js names them for the operator (a role without one is shown
# by its name)
ROLE_WORDS = {"vread": "voltage read", "iread": "current read", "value": "value", "p": "pressure",
              "speed": "speed", "current": "current", "flow": "flow", "pv": "measured value",
              "out": "output", "sp_cmd": "set point"}
LOG_UNITS = {"torr", "mbar", "pa"}                                             # fields/format spansDecades
DATASOURCE = {"type": "grafana-postgresql-datasource", "uid": "mist2log"}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower())


def sql_text(text):
    return "'" + text.replace("'", "''") + "'"


def installed(reg):
    return [d for d, dev in reg["devices"].items() if not dev["flags"].get("not_installed")]


def trend_pvs(reg, did):
    """(PV, role of its graph, unit of its graph, legend) of every trend of a device; a set point
    of trends.beside goes into the graph of its read-back."""
    dev = reg["devices"][did]
    beside = reg["trends"].get("beside") or {}
    scopes = [(None, dev["roles"])] + [(ch, c["roles"]) for ch, c in (dev.get("channels") or {}).items() if not c.get("spare")]
    logged = lambda name: name and dev["pvs"][name].get("log", "none") != "none"
    out = []
    for ch, roles in scopes:
        for role in reg["trends"]["roles"]:
            name = roles.get(role)
            if logged(name):
                label = dev["name"] if ch is None else (dev["channels"][ch]["label"] or "%s %s" % (dev["name"], ch))
                egu = dev["pvs"][name].get("egu", "")
                out.append((name, role, egu, label))
                if logged(roles.get(beside.get(role))):
                    out.append((roles[beside[role]], role, egu, "%s %s" % (label, ROLE_WORDS.get(beside[role], beside[role]))))
    return out


def trend_panel(pvs, role, egu, grid):
    values = ", ".join("(%s, %s)" % (sql_text(n), sql_text(label)) for n, _, _, label in pvs)
    query = ("SELECT t.\"time\", l.label AS metric, t.value\n"
             "FROM log_trend(ARRAY[%s], $__timeFrom(), $__timeTo(), $__interval_ms) t\n"
             "JOIN (VALUES %s) l(pv, label) ON l.pv = t.metric\nORDER BY 1"
             % (", ".join(sql_text(n) for n, _, _, _ in pvs), values))
    log = egu.lower() in LOG_UNITS
    return {"type": "timeseries", "title": ROLE_WORDS.get(role, role) + (" (%s)" % egu if egu else ""),
            "datasource": DATASOURCE, "gridPos": grid,
            "targets": [{"refId": "A", "datasource": DATASOURCE, "format": "time_series", "rawQuery": True,
                         "editorMode": "code", "rawSql": query}],
            "fieldConfig": {"defaults": {"unit": egu or "none", "custom": {
                "spanNulls": False, "showPoints": "never", "lineInterpolation": "stepAfter",
                "scaleDistribution": {"type": "log", "log": 10} if log else {"type": "linear"}}}, "overrides": []},
            "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}}}


def event_panel(devices, grid, title="Event log"):
    where = "" if devices is None else "\n  AND device = ANY(ARRAY[%s])" % ", ".join(sql_text(d) for d in devices)
    query = ("SELECT t AS \"time\", kind, pv, device, old, new, severity, detail\nFROM event_log\n"
             "WHERE $__timeFilter(t)%s\nORDER BY t DESC\nLIMIT 1000" % where)
    return {"type": "table", "title": title, "datasource": DATASOURCE, "gridPos": grid,
            "targets": [{"refId": "A", "datasource": DATASOURCE, "format": "table", "rawQuery": True,
                         "editorMode": "code", "rawSql": query}], "options": {"showHeader": True}}


def dashboard(title, panels, variables=()):
    for i, panel in enumerate(panels, 1):
        panel["id"] = i
    return {"uid": slug(title), "title": title, "tags": ["mist2"], "editable": False, "schemaVersion": 39,
            "time": {"from": "now-1h", "to": "now"}, "refresh": "10s", "timezone": "browser",
            "templating": {"list": list(variables)}, "panels": panels,
            "description": "Generated by logger/mist2log/dashboards.py from the registry. Do not edit."}


def page_dashboard(reg, title, devices):
    pvs = [p for d in devices for p in trend_pvs(reg, d)]
    groups = {}
    for p in dict((p[0], p) for p in pvs).values():           # a PV once
        groups.setdefault((p[1], p[2].lower()), []).append(p)
    panels = []
    for i, ((role, _), group) in enumerate(groups.items()):
        panels.append(trend_panel(group, role, group[0][2], {"x": 12 * (i % 2), "y": 9 * (i // 2), "w": 12, "h": 9}))
    panels.append(event_panel(devices, {"x": 0, "y": 9 * ((len(groups) + 1) // 2), "w": 24, "h": 10}))
    return dashboard(title, panels)


def build(reg):
    devices = installed(reg)
    # A device without a page (a service of the control system, such as the logger itself) is
    # infrastructure, as in the GUI (registry.js isInfrastructure): no dashboard of its own, not
    # in the Overview; its events are in Infrastructure.
    drawn = [d for d in devices if reg["devices"][d]["page"]]
    pages = list(dict.fromkeys(reg["devices"][d]["page"] for d in drawn))
    out = [page_dashboard(reg, "Overview", drawn)]
    out += [page_dashboard(reg, page, [d for d in devices if reg["devices"][d]["page"] == page]) for page in pages]
    variable = {"type": "query", "name": "pv", "label": "PVs", "datasource": DATASOURCE, "multi": True,
                "includeAll": False, "refresh": 1, "query": "SELECT name FROM pv WHERE tier IN ('raw', 'seconds', 'minutes') ORDER BY name",
                "definition": "logged PVs with a trend"}
    trends = trend_panel([("$pv", "", "", "")], "", "", {"x": 0, "y": 0, "w": 24, "h": 14})
    trends["title"] = "Trend of the PVs picked"
    trends["targets"][0]["rawSql"] = ("SELECT \"time\", metric, value\nFROM log_trend(ARRAY[${pv:sqlstring}]::text[], "
                                      "$__timeFrom(), $__timeTo(), $__interval_ms)\nORDER BY 1")
    out.append(dashboard("Trends", [trends, event_panel(None, {"x": 0, "y": 14, "w": 24, "h": 10})], [variable]))
    missing = {"type": "table", "title": "Logged PVs not connected", "datasource": DATASOURCE,
               "gridPos": {"x": 0, "y": 0, "w": 24, "h": 8},
               "targets": [{"refId": "A", "datasource": DATASOURCE, "format": "table", "rawQuery": True, "editorMode": "code",
                            "rawSql": "SELECT name, device, since FROM pv WHERE tier <> 'none' AND NOT connected ORDER BY name"}]}
    out.append(dashboard("Infrastructure", [missing, event_panel(None, {"x": 0, "y": 8, "w": 24, "h": 12},
                                                                "Event log (every device and the logger)")]))
    return out


def main():
    registry, out_dir = sys.argv[1:3]
    with open(registry, encoding="utf-8") as handle:
        reg = json.load(handle)
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        if name.endswith(".json"):
            os.remove(os.path.join(out_dir, name))
    boards = build(reg)
    for board in boards:
        with open(os.path.join(out_dir, board["uid"] + ".json"), "w", encoding="utf-8") as handle:
            json.dump(board, handle, indent=1)
    print("dashboards.py: %d dashboards -> %s (%s)" % (len(boards), out_dir, ", ".join(b["title"] for b in boards)))


if __name__ == "__main__":
    main()
