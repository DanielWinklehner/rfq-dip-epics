"""The Grafana dashboards build from the registry as it is (mist2log/dashboards.py), with the
pages and graphs of the GUI. No emulation, no database."""
import json
import os

from mist2log import dashboards

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
REGISTRY = os.path.join(REPO, "RAS", "mist2", "ReactApp", "src", "registry", "registry.json")


def registry():
    with open(REGISTRY, encoding="utf-8") as handle:
        return json.load(handle)


def test_one_dashboard_per_page_of_the_gui():
    reg = registry()
    boards = dashboards.build(reg)
    # the tabs as RAS/mist2/tools/gui-check.mjs computes them: pages of the installed devices,
    # without the devices that have none (infrastructure)
    installed = [d for d, dev in reg["devices"].items() if not dev["flags"].get("not_installed")]
    pages = ["Overview"] + list(dict.fromkeys(p for p in (reg["devices"][d]["page"] for d in installed) if p)) + \
        ["Trends", "Infrastructure"]
    assert [b["title"] for b in boards] == pages
    assert len({b["uid"] for b in boards}) == len(boards)
    assert any(not dev["page"] for dev in reg["devices"].values()), "the registry has a device without a page"


def test_the_loop_has_its_measured_value_with_its_set_point_and_its_output():
    reg = registry()
    board = next(b for b in dashboards.build(reg) if b["title"] == "Plasma generator")
    loop = next(dev for dev in reg["devices"].values() if dev.get("drives"))
    graphs = [p["targets"][0]["rawSql"] for p in board["panels"] if p["type"] == "timeseries"]
    assert any("ARRAY['%s', '%s']" % (loop["roles"]["pv"], loop["roles"]["sp_cmd"]) in g for g in graphs), graphs
    assert any("ARRAY['%s']" % loop["roles"]["out"] in g for g in graphs), graphs
