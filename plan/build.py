#!/usr/bin/env python3
"""Generate the MIST-2 control system sketches and the Word document from controls.yaml.

    python build.py                 # everything into out/
    python build.py --no-docx       # sketches only
    python build.py --db-dir DIR    # read the databases from DIR instead of EPICS/Db

Existing PVs are read from the databases in EPICS/Db, with the macros of the database loads that
controls.yaml gives each device. Those loads are compared with the dbLoadRecords lines of the
st.cmd files named by the hosts, and every record of a loaded database must have a role or be
marked internal (section "databases" of controls.yaml). Every difference is printed as a WARNING.

Needs: Python 3.9+, PyYAML, python-docx, and Graphviz ("dot") on the PATH.
"""
import argparse
import html
import os
import re
import shutil
import subprocess
import sys
import zipfile

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

STATUS = {  # label, fill, border, dashed
    "keep":    ("KEEP",    "#FFFFFF", "#555555", False),
    "modify":  ("MODIFY",  "#FFF2CC", "#B58900", False),
    "replace": ("REPLACE", "#F8D7DA", "#B03A2E", False),
    "new":     ("NEW",     "#D5F5E3", "#1E8449", False),
    "later":   ("PHASE 2", "#D6EAF8", "#2E86C1", True),
    "tbd":     ("TBD",     "#ECECEC", "#777777", True),
}
STATUS_TEXT = {
    "keep": "stays as it is", "modify": "stays, with changes", "replace": "will be removed",
    "new": "to be added", "later": "phase 2", "tbd": "open, information missing",
}
WRITE_TYPES = {"ao", "bo", "longout", "mbbo", "stringout", "aao"}
FLAGS = {"not_polled": "Not polled", "assumed": "Assumed"}  # device flags, shown by the GUI
FONT = "Helvetica"
MONO = "Courier"


# ----------------------------------------------------------------------------- model
def expand(text, macros, undefined=None):
    """EPICS macro expansion: $(NAME), ${NAME}, defaults $(NAME=default), nested defaults."""
    out, i = [], 0
    while i < len(text):
        if text.startswith(("$(", "${"), i):
            depth, j = 1, i + 2
            while j < len(text) and depth:
                depth += {"(": 1, "{": 1, ")": -1, "}": -1}.get(text[j], 0)
                j += 1
            name, has_default, default = text[i + 2:j - 1].partition("=")
            if name in macros:
                out.append(str(macros[name]))
            elif has_default:
                out.append(expand(default, macros, undefined))
            else:
                out.append(text[i:j])
                if undefined is not None:
                    undefined.add(name)
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def record_key(template):
    """Name of a record in its database without the prefix macro: $(DEV=AU-20P7)-$(UNITNUM):voltage:get -> voltage:get."""
    return re.sub(r"^(?:\$[({][^)}]*[)}][-:]?)+", "", template)


class DbError(Exception):
    """A database the parser does not understand, or whose records it did not all find."""


def tokens(text, name):
    """Tokens of a database file: (kind, value, line). kind is 'str' (quoted), 'word' or one of ( ) { } ,"""
    i, line, out = 0, 1, []
    while i < len(text):
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif c == "#":                                   # comment to the end of the line
            while i < len(text) and text[i] != "\n":
                i += 1
        elif c == '"':
            j = i + 1
            while j < len(text) and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            if j >= len(text):
                raise DbError("%s line %d: string without its closing quote" % (name, line))
            out.append(("str", text[i + 1:j], line))
            line += text.count("\n", i, j)
            i = j + 1
        elif c in "(){},":
            out.append((c, c, line))
            i += 1
        else:                                            # bare word, may hold $(macro) or ${macro}
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in '(){},"#':
                if text.startswith(("$(", "${"), j):
                    depth, j = 1, j + 2
                    while j < len(text) and depth:
                        depth += {"(": 1, "{": 1, ")": -1, "}": -1}.get(text[j], 0)
                        j += 1
                else:
                    j += 1
            out.append(("word", text[i:j], line))
            i = j
    return out


def simple_record_names(text):
    """Independent rough scan: the names of all record( and grecord( statements, comments cut at '#'."""
    text = re.sub(r"#[^\n]*", "", text)
    return re.findall(r'\bg?record\s*\(\s*[^,()]*,\s*"?([^"\s)]+)', text)


def parse_db(path, macros, undefined=None):
    """Records of an EPICS database as a list of dicts, macros expanded. Raises DbError for anything
    the parser does not understand, and when the rough scan finds a record the parser did not."""
    name = os.path.basename(path)
    with open(path, errors="replace") as handle:
        text = handle.read().replace("\r", "")
    toks, pos = tokens(text, name), [0]

    def take(*kinds):
        if pos[0] >= len(toks):
            raise DbError("%s: unexpected end of file" % name)
        tok = toks[pos[0]]
        if tok[0] not in kinds:
            raise DbError("%s line %d: expected %s, found %r" % (name, tok[2], " or ".join(kinds), tok[1]))
        pos[0] += 1
        return tok

    def peek(kind):
        return pos[0] < len(toks) and toks[pos[0]][0] == kind

    def args(count):
        take("(")
        values = [take("str", "word")[1]]
        for _ in range(count - 1):
            take(",")
            values.append(take("str", "word")[1])
        take(")")
        return values

    records, aliases = [], []
    while pos[0] < len(toks):
        word, line = take("word")[1:]
        if word in ("record", "grecord"):
            rtype, template = args(2)
            fields, info, own_aliases = {}, {}, []
            if peek("{"):
                take("{")
                while not peek("}"):
                    item, item_line = take("word")[1:]
                    if item == "field":
                        key, value = args(2)
                        fields[key] = expand(value, macros, undefined)
                    elif item == "info":
                        key, value = args(2)
                        info[key] = value
                    elif item == "alias":
                        own_aliases.append(expand(args(1)[0], macros, undefined))
                    else:
                        raise DbError("%s line %d: %r in the body of record %s is not field, info or alias"
                                      % (name, item_line, item, template))
                take("}")
            records.append({"name": expand(template, macros, undefined), "key": record_key(template), "type": rtype,
                            "egu": fields.get("EGU", ""), "desc": fields.get("DESC", ""), "scan": fields.get("SCAN", ""),
                            "fields": fields, "info": info, "aliases": own_aliases, "state": "existing"})
        elif word == "alias":
            target, alias = args(2)
            aliases.append((expand(target, macros, undefined), expand(alias, macros, undefined), line))
        else:
            raise DbError("%s line %d: statement %r is not understood (only record, grecord and alias are)" % (name, line, word))
    by_name = {rec["name"]: rec for rec in records}
    for target, alias, line in aliases:
        if target not in by_name:
            raise DbError("%s line %d: alias %s for record %s, which this file does not define" % (name, line, alias, target))
        by_name[target]["aliases"].append(alias)
    scanned = simple_record_names(text)
    if len(scanned) != len(records):
        parsed = [record_key(r["key"]) for r in records]
        missed = [n for n in scanned if record_key(n) not in parsed] or ["(names not told apart)"]
        raise DbError("%s: a plain scan finds %d record statements, the parser %d. Missed: %s"
                      % (name, len(scanned), len(records), ", ".join(missed)))
    return records


def loads_of(entry):
    """The database loads of a device or host: 'epics' is one {db, macros} or a list of them."""
    epics = entry.get("epics") or []
    return epics if isinstance(epics, list) else [epics]


def fmt_macros(macros):
    return ",".join("%s=%s" % item for item in macros.items())


def parse_st_cmd(path):
    """dbLoadRecords lines of a st.cmd: list of (line number, database file name, macros)."""
    loads = []
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            found = re.match(r'\s*dbLoadRecords\(\s*"([^"]+)"\s*(?:,\s*"([^"]*)")?\s*\)', line)
            if found:
                macros = {}
                for item in filter(None, (found.group(2) or "").split(",")):
                    key, _, value = item.partition("=")
                    macros[key.strip()] = value.strip().strip("'\"")
                loads.append((number, os.path.basename(found.group(1)), macros))
    return loads


def role_spec(spec):
    """A role is a record name, or {record, readback, test, ack, note} for a record that is written."""
    return spec if isinstance(spec, dict) else {"record": spec}


def channel_roles(rule, keys):
    """Channels of a database rule, expanded over the records that exist: {channel: {role: (key, spec)}}."""
    channels = {}
    for template, members in (rule.get("channels") or {}).items():
        numbers = set()
        for spec in members.values():
            pattern = re.escape(role_spec(spec)["record"]).replace(re.escape("<n>"), r"(\d+)")
            for key in keys:
                found = re.fullmatch(pattern, key)
                if found:
                    numbers.add(found.group(1) if found.groups() else "")
        for n in sorted(numbers, key=lambda n: (len(n), n)):
            channel = channels.setdefault(template.replace("<n>", n), {})
            for role, spec in members.items():
                key = role_spec(spec)["record"].replace("<n>", n)
                if key in keys:
                    channel[role] = (key, role_spec(spec))
    return channels


class Model:
    def __init__(self, path, db_dir):
        with open(path, encoding="utf-8") as handle:
            self.d = yaml.safe_load(handle)
        self.db_dir = db_dir
        self.devices = self.d["devices"]
        self.hosts = {h["id"]: h for h in self.d["hosts"]}
        self.adapters = {a["id"]: a for a in self.d.get("adapters", [])}
        self.rules = self.d.get("databases") or {}
        self.by_id = {dev["id"]: dev for dev in self.devices}
        self.warnings = []
        # Owners of database loads: devices, and hosts for the records of the IOC itself.
        self.owners = [o for o in self.devices + self.d["hosts"] if loads_of(o)]
        for owner in self.d["hosts"] + self.devices:
            owner["pvs"] = self._pvs(owner)
        self._check()
        self._check_roles()
        self._check_loads()
        self.warnings = list(dict.fromkeys(self.warnings))   # the same problem once, even if several devices load the file

    def _db(self, name, macros, owner):
        path = os.path.join(self.db_dir, name)
        if not os.path.exists(path):
            self.warnings.append("%s: database %s not found in %s" % (owner, name, self.db_dir))
            return []
        undefined = set()
        try:
            pvs = parse_db(path, macros, undefined)
        except DbError as error:
            self.warnings.append(str(error))
            return []
        for macro in sorted(undefined):
            self.warnings.append("%s: %s needs macro %s, the load in controls.yaml does not give it" % (owner, name, macro))
        return pvs

    def macros(self, load):
        """Macros of one load: the database's common macros (databases: <db>: macros), then the device's."""
        return dict((self.rules.get(load["db"]) or {}).get("macros") or {}, **(load.get("macros") or {}))

    def _pvs(self, owner):
        pvs = []
        for load in loads_of(owner):
            rule = self.rules.get(load["db"]) or {}
            records = self._db(load["db"], self.macros(load), owner["id"])
            by_key = {pv["key"]: pv for pv in records}
            for role, spec in (rule.get("roles") or {}).items():
                if role_spec(spec)["record"] in by_key:
                    by_key[role_spec(spec)["record"]].update(role=role, spec=role_spec(spec))
            for channel, members in channel_roles(rule, by_key).items():
                for role, (key, spec) in members.items():
                    by_key[key].update(role=role, channel=channel, spec=spec)
            for key in rule.get("internal") or []:
                if key in by_key:
                    by_key[key]["internal"] = True
            for pv in records:
                pv.update(db=load["db"], load=load, cls=rule.get("class"))
            pvs += records
        if owner.get("inherits_pvs_from"):
            for pv in self.by_id[owner["inherits_pvs_from"]]["pvs"]:
                if pv["state"] == "existing":
                    pvs.append(dict(pv, state="reuse"))
        if owner.get("libcom1") and loads_of(owner) and "libcom1_device.db" not in [l["db"] for l in loads_of(owner)]:
            for pv in self._db("libcom1_device.db", loads_of(owner)[0].get("macros", {}), owner["id"]):
                pvs.append(dict(pv, state="proposed", remark="database exists: libcom1_device.db"))
        for pv in owner.get("proposed", []):
            pvs.append({"name": pv["name"], "type": pv.get("type", ""), "egu": pv.get("egu", ""),
                        "desc": pv.get("desc", ""), "scan": "", "state": "proposed", "remark": pv.get("remark", "")})
        return pvs

    def _check(self):
        seen = {}
        for dev in self.devices:
            for key in ("subsystem", "location", "host", "status"):
                if key not in dev:
                    self.warnings.append("device %s has no %s" % (dev["id"], key))
            if dev.get("status") not in STATUS:
                self.warnings.append("device %s: unknown status %r" % (dev["id"], dev.get("status")))
            if dev.get("host") not in self.hosts:
                self.warnings.append("device %s: unknown host %r" % (dev["id"], dev.get("host")))
            if dev.get("via") and dev["via"] not in self.adapters:
                self.warnings.append("device %s: unknown adapter %r" % (dev["id"], dev["via"]))
            for flag in dev.get("flags") or {}:
                if flag not in FLAGS:
                    self.warnings.append("device %s: unknown flag %r (known: %s)" % (dev["id"], flag, ", ".join(FLAGS)))
        for owner in self.d["hosts"] + self.devices:
            for pv in owner["pvs"]:
                if pv["state"] == "existing":
                    for name in [pv["name"]] + pv.get("aliases", []):
                        if name in seen and seen[name] != owner["id"]:
                            self.warnings.append("PV %s is defined by %s and %s" % (name, seen[name], owner["id"]))
                        seen[name] = owner["id"]

    def _check_roles(self):
        """Every record of a loaded database has a role or is internal; every rule names a record that exists."""
        users = {}
        for owner in self.owners:
            for load in loads_of(owner):
                users.setdefault(load["db"], []).append(owner["id"])
        for db, owners in users.items():
            path = os.path.join(self.db_dir, db)
            if not os.path.exists(path):
                continue
            who = "%s (loaded by %s)" % (db, ", ".join(sorted(set(owners))))
            rule = self.rules.get(db)
            if rule is None:
                self.warnings.append("%s: no entry under 'databases:' in controls.yaml, so no record has a role" % who)
                continue
            try:
                records = parse_db(path, {})
            except DbError:
                continue  # reported by _db
            keys = [pv["key"] for pv in records]
            named = {}
            for role, spec in (rule.get("roles") or {}).items():
                named[role_spec(spec)["record"]] = ("role", role, role_spec(spec))
            channels = channel_roles(rule, keys)
            for template in rule.get("channels") or {}:
                if not any(re.fullmatch(re.escape(template).replace(re.escape("<n>"), r"\d+"), ch) for ch in channels):
                    self.warnings.append("%s: channel %s in controls.yaml matches no record" % (who, template))
            for channel, members in channels.items():
                for role, (key, spec) in members.items():
                    named[key] = ("role", role, spec)
            for key in rule.get("internal") or []:
                named.setdefault(key, ("internal", None, {}))
            for key in named:
                if key not in keys:
                    self.warnings.append("%s: controls.yaml names record %s, which the database does not have" % (who, key))
            for rec in records:
                kind, role, spec = named.get(rec["key"], (None, None, None))
                if kind is None:
                    self.warnings.append("%s: record %s has no role and is not internal. Add it under "
                                         "'databases: %s' in controls.yaml (roles, channels or internal)" % (who, rec["key"], db))
                elif kind == "role" and rec["type"] in WRITE_TYPES and ("test" not in spec or "ack" not in spec):
                    self.warnings.append("%s: record %s is written (role %s) but has no 'test' range or no 'ack' in controls.yaml"
                                         % (who, rec["key"], role))
        for owner in self.owners:
            classes = sorted({pv["cls"] for pv in owner["pvs"] if pv.get("cls")})
            if len(classes) > 1:
                self.warnings.append("%s: its databases give more than one widget class: %s" % (owner["id"], ", ".join(classes)))
            known = {pv.get("channel") for pv in owner["pvs"]} | {pv.get("role") for pv in owner["pvs"]}
            for label in owner.get("labels") or {}:
                if label not in known:
                    self.warnings.append("%s: label for %r, which is no channel and no role of the device" % (owner["id"], label))

    def _check_loads(self):
        """The loads in controls.yaml against the dbLoadRecords lines of the st.cmd files, in both directions."""
        started = {}
        for host in self.d["hosts"]:
            if host.get("st_cmd"):
                path = os.path.join(REPO, host["st_cmd"])
                if not os.path.exists(path):
                    self.warnings.append("host %s: st.cmd %s not found" % (host["id"], host["st_cmd"]))
                    continue
                for number, db, macros in parse_st_cmd(path):
                    started.setdefault(host["id"], []).append(
                        {"host": host["id"], "where": "%s line %d" % (host["st_cmd"], number), "db": db, "macros": macros})
        lines = [s for host_lines in started.values() for s in host_lines]
        planned = []
        for owner in self.owners:
            host = owner["id"] if owner in self.d["hosts"] else owner.get("host")
            if not (self.hosts.get(host) or {}).get("st_cmd"):
                self.warnings.append("%s: has database loads, but its host %s names no st_cmd" % (owner["id"], host))
                continue
            for load in loads_of(owner):
                macros = {k: str(v) for k, v in self.macros(load).items()}
                planned.append({"owner": owner["id"], "host": host, "db": load["db"], "macros": macros})
        unmatched = []
        for y in planned:
            same = [s for s in lines if s["db"] == y["db"] and s["macros"] == y["macros"] and s["host"] == y["host"]]
            if same:
                lines.remove(same[0])
            else:
                unmatched.append(y)
        for y in unmatched:
            def score(s):
                return (sum(1 for k, v in y["macros"].items() if s["macros"].get(k) == v), s["host"] == y["host"])
            candidates = sorted([s for s in lines if s["db"] == y["db"]], key=score, reverse=True)
            if not candidates or (score(candidates[0])[0] == 0 and len(candidates) > 1):
                self.warnings.append("device %s: controls.yaml loads %s (%s) on %s, but %s has no such dbLoadRecords line"
                                     % (y["owner"], y["db"], fmt_macros(y["macros"]), y["host"], self.hosts[y["host"]]["st_cmd"]))
                continue
            s = candidates[0]
            lines.remove(s)
            if s["macros"] != y["macros"]:
                diff = []
                for key in sorted(set(y["macros"]) | set(s["macros"])):
                    if key not in y["macros"]:
                        diff.append("st.cmd has %s=%s, controls.yaml has not" % (key, s["macros"][key]))
                    elif key not in s["macros"]:
                        diff.append("controls.yaml has %s=%s, st.cmd has not" % (key, y["macros"][key]))
                    elif y["macros"][key] != s["macros"][key]:
                        diff.append("%s is %s in st.cmd, %s in controls.yaml" % (key, s["macros"][key], y["macros"][key]))
                self.warnings.append("device %s: macros of %s differ from %s: %s. Fix the device's 'epics' entry in "
                                     "controls.yaml (or 'databases: %s: macros' for every device that loads it)"
                                     % (y["owner"], y["db"], s["where"], "; ".join(diff), y["db"]))
            if s["host"] != y["host"]:
                self.warnings.append("device %s is on host %s in controls.yaml, but %s (%s) is loaded by %s (host %s)"
                                     % (y["owner"], y["host"], y["db"], fmt_macros(y["macros"]), s["where"], s["host"]))
        for s in lines:
            self.warnings.append("%s: %s (%s) is claimed by no device or host in controls.yaml"
                                 % (s["where"], s["db"], fmt_macros(s["macros"])))

    def public(self, owner):
        """The PVs of a device without its internal records."""
        return [pv for pv in owner["pvs"] if not pv.get("internal")]

    def counts(self, dev):
        existing = sum(1 for pv in self.public(dev) if pv["state"] in ("existing", "reuse"))
        proposed = sum(1 for pv in dev["pvs"] if pv["state"] == "proposed")
        return existing, proposed


# ----------------------------------------------------------------------------- graphviz
def esc(text):
    return html.escape(str(text), quote=False)


def edge_label(text, width=26):
    """Link text for an edge: wrapped, and safe inside a quoted dot string."""
    return _wrap(str(text).replace('"', "'"), width).replace("\n", "\\n")


def node_style(status):
    label, fill, border, dashed = STATUS[status]
    style = "rounded,filled" + (",dashed" if dashed else "")
    return 'style="%s", fillcolor="%s", color="%s"' % (style, fill, border)


def box_label(title, lines, status=None, extra=None):
    rows = ['<TR><TD ALIGN="LEFT"><B>%s</B></TD></TR>' % esc(title)]
    for line in lines:
        if line:
            rows.append('<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9">%s</FONT></TD></TR>' % esc(line))
    tail = []
    if status:
        tail.append(STATUS[status][0])
    if extra:
        tail.append(extra)
    if tail:
        rows.append('<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="8" COLOR="%s"><B>%s</B></FONT></TD></TR>'
                    % (STATUS[status][2] if status else "#555555", esc("  |  ".join(tail))))
    return '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="1">%s</TABLE>>' % "".join(rows)


def legend_node(with_pvs):
    rows = ['<TR><TD COLSPAN="2" ALIGN="LEFT"><B>Legend</B></TD></TR>']
    for key in ("keep", "modify", "replace", "new", "later", "tbd"):
        label, fill, border, _ = STATUS[key]
        rows.append('<TR><TD BGCOLOR="%s" BORDER="1" COLOR="%s"><FONT POINT-SIZE="8"><B>%s</B></FONT></TD>'
                    '<TD ALIGN="LEFT"><FONT POINT-SIZE="9">%s</FONT></TD></TR>' % (fill, border, label, esc(STATUS_TEXT[key])))
    if with_pvs:
        rows.append('<TR><TD ALIGN="LEFT"><FONT FACE="%s" POINT-SIZE="9">name</FONT></TD>'
                    '<TD ALIGN="LEFT"><FONT POINT-SIZE="9">PV that exists today</FONT></TD></TR>' % MONO)
        rows.append('<TR><TD ALIGN="LEFT"><FONT FACE="%s" POINT-SIZE="9" COLOR="#1E8449">+ name</FONT></TD>'
                    '<TD ALIGN="LEFT"><FONT POINT-SIZE="9">proposed PV</FONT></TD></TR>' % MONO)
    return ('legend [shape=plain, label=<<TABLE BORDER="1" COLOR="#999999" CELLBORDER="0" CELLSPACING="2" '
            'CELLPADDING="3" BGCOLOR="#FFFFFF">%s</TABLE>>];' % "".join(rows))


HEADER = """digraph G {
  rankdir=LR; compound=true; nodesep=0.22; ranksep=%s; newrank=true;
  graph [fontname="%s", fontsize=13, labelloc=t, labeljust=l, pad=0.2, bgcolor="white"];
  node  [fontname="%s", fontsize=10, shape=box, margin="0.10,0.05"];
  edge  [fontname="%s", fontsize=8, color="#555555", fontcolor="#333333", arrowsize=0.6];
"""


def overview_dot(m):
    out = [HEADER % ("0.75", FONT, FONT, FONT)]
    meta = m.d["meta"]
    out.append('  label=<<B>%s</B>: devices and connections (rev. %s, %s)>;' % (esc(meta["title"]), esc(meta["revision"]), esc(meta["date"])))
    net = m.d.get("network", {})
    out.append('  lan [label=<<B>%s</B><BR/><FONT POINT-SIZE="9">%s</FONT>>, ' % (esc(net.get("name", "Control network")), esc(_wrap(net.get("text", "Ethernet, EPICS Channel Access"), 30)).replace("\n", "<BR/>")) +
               'style="filled", fillcolor="#EAECEE", color="#555555", height=1.2];')
    for loc in m.d["locations"]:
        out.append('  subgraph cluster_%s { label=<<B>%s</B>>; style="rounded"; color="#999999"; bgcolor="#FAFAFA";' % (loc["id"], esc(loc["name"])))
        for host in m.d["hosts"]:
            if host["location"] == loc["id"]:
                out.append('    %s [label=%s, %s, penwidth=2];' % (host["id"], box_label(
                    host["name"], [host.get("model", ""), "OS: " + host.get("os", "?")], host["status"], "IOC / computer"), node_style(host["status"])))
        for adapter in m.adapters.values():
            if m.hosts[adapter["host"]]["location"] == loc["id"]:
                out.append('    %s [label=%s, %s, shape=box];' % (adapter["id"], box_label(
                    adapter["name"], [adapter.get("text", "")], adapter["status"], "adapter"), node_style(adapter["status"])))
        for dev in m.devices:
            if dev["location"] == loc["id"]:
                existing, proposed = m.counts(dev)
                pvs = "PVs: %s%s" % ("?" if dev.get("pvs_unknown") else existing, " (+%d)" % proposed if proposed else "")
                out.append('    %s [label=%s, %s];' % (dev["id"], box_label(dev["name"], [dev.get("model", "")], dev["status"], pvs), node_style(dev["status"])))
        out.append("  }")
    for host in m.d["hosts"]:
        out.append('  lan -> %s [dir=none, penwidth=1.6, label="%s"];' % (host["id"], edge_label(host.get("uplink", ""))))
    for adapter in m.adapters.values():
        out.append('  %s -> %s [label="%s"];' % (adapter["host"], adapter["id"], edge_label(adapter.get("link", ""))))
    for dev in m.devices:
        src = dev.get("via") or dev["host"]
        style = ', style=dashed' if dev["status"] in ("later", "tbd", "new") else ""
        out.append('  %s -> %s [label="%s"%s];' % (src, dev["id"], edge_label(dev.get("link", "")), style))
    out.append("  " + legend_node(False))
    out.append("  { rank=same; lan; legend; }")
    out.append("}")
    return "\n".join(out)


def group_pvs(pvs):
    """Collapse s1..s8 style series so that the sketches stay readable."""
    groups, order = {}, []
    for pv in pvs:
        parts = pv["name"].split(":")
        key = None
        if len(parts) >= 3:
            found = re.match(r"^([A-Za-z]+)(\d+)$", parts[1])
            if found:
                key = (parts[0], found.group(1), ":".join(parts[2:]), pv["type"], pv["state"])
        if key is None:
            key = ("single", pv["name"], pv["state"])
            groups[key] = dict(pv)
            order.append(key)
            continue
        if key not in groups:
            groups[key] = dict(pv, first=int(found.group(2)), last=int(found.group(2)), n=1)
            order.append(key)
        else:
            groups[key]["last"] = int(found.group(2))
            groups[key]["n"] += 1
    rows = []
    for key in order:
        pv = groups[key]
        if pv.get("n", 1) > 1:
            pv["name"] = "%s:%s%d..%d:%s" % (key[0], key[1], pv["first"], pv["last"], key[2])
            pv["desc"] = re.sub(r"\b%s%d\b" % (key[1], pv["first"]), key[1] + "N", pv["desc"])
            pv["desc"] = re.sub(r"\b(\w+ )%d\b" % pv["first"], r"\1N", pv["desc"])
        rows.append(pv)
    return rows


def pv_table(dev, m):
    label, fill, border, dashed = STATUS[dev["status"]]
    rows = ['<TR><TD COLSPAN="3" ALIGN="LEFT" BGCOLOR="%s"><B>%s</B>&nbsp;&nbsp;<FONT POINT-SIZE="8" COLOR="%s"><B>%s</B></FONT></TD></TR>'
            % (fill, esc(dev["name"]), border, label),
            '<TR><TD COLSPAN="3" ALIGN="LEFT" BGCOLOR="%s"><FONT POINT-SIZE="9">%s</FONT></TD></TR>' % (fill, esc(dev.get("model", ""))),
            '<TR><TD COLSPAN="3" ALIGN="LEFT" BGCOLOR="%s"><FONT POINT-SIZE="8" COLOR="#444444">%s</FONT></TD></TR>' % (fill, esc(dev.get("protocol", "")))]
    if dev.get("pvs_unknown"):
        rows.append('<TR><TD COLSPAN="3" ALIGN="LEFT"><FONT POINT-SIZE="9" COLOR="#777777"><I>existing PVs: not in the repository</I></FONT></TD></TR>')
    for pv in group_pvs(m.public(dev)):
        color = {"existing": "#000000", "reuse": "#000000", "proposed": "#1E8449"}[pv["state"]]
        if dev["status"] == "replace":
            color = "#888888"
        prefix = "+ " if pv["state"] == "proposed" else ""
        io = "W" if pv["type"] in WRITE_TYPES else "R"
        unit = " [%s]" % pv["egu"] if pv["egu"] else ""
        rows.append('<TR><TD ALIGN="LEFT"><FONT FACE="%s" POINT-SIZE="9" COLOR="%s">%s%s</FONT></TD>'
                    '<TD><FONT POINT-SIZE="8" COLOR="%s">%s</FONT></TD>'
                    '<TD ALIGN="LEFT"><FONT POINT-SIZE="8" COLOR="%s">%s%s</FONT></TD></TR>'
                    % (MONO, color, prefix, esc(pv["name"]), color, io, color, esc(_short(pv["desc"], 46)), esc(unit)))
    if not m.public(dev) and not dev.get("pvs_unknown"):
        rows.append('<TR><TD COLSPAN="3" ALIGN="LEFT"><FONT POINT-SIZE="9" COLOR="#777777"><I>no PVs yet</I></FONT></TD></TR>')
    return ('<<TABLE BORDER="1" COLOR="%s" CELLBORDER="0" CELLSPACING="0" CELLPADDING="3" BGCOLOR="#FFFFFF"%s>%s</TABLE>>'
            % (border, ' STYLE="dashed"' if dashed else "", "".join(rows)))


def subsystem_dot(m, sub):
    devs = [dev for dev in m.devices if dev["subsystem"] == sub["id"]]
    out = [HEADER % ("0.8", FONT, FONT, FONT)]
    out.append('  label=<<B>%s</B>: process variables (R = read, W = write)>;' % esc(sub["name"]))
    used_hosts, used_adapters = [], []
    for dev in devs:
        if dev["host"] not in used_hosts:
            used_hosts.append(dev["host"])
        if dev.get("via") and dev["via"] not in used_adapters:
            used_adapters.append(dev["via"])
    for hid in used_hosts:
        host = m.hosts[hid]
        out.append('  %s [label=%s, %s, penwidth=2];' % (hid, box_label(host["name"], [host.get("model", ""), "OS: " + host.get("os", "?")], host["status"], "IOC / computer"), node_style(host["status"])))
    for aid in used_adapters:
        adapter = m.adapters[aid]
        out.append('  %s [label=%s, %s];' % (aid, box_label(adapter["name"], [adapter.get("text", "")], adapter["status"], "adapter"), node_style(adapter["status"])))
        out.append('  %s -> %s [label="%s"];' % (adapter["host"], aid, edge_label(adapter.get("link", ""))))
    for dev in devs:
        out.append('  %s [shape=plain, label=%s];' % (dev["id"], pv_table(dev, m)))
        out.append('  %s -> %s [label="%s"];' % (dev.get("via") or dev["host"], dev["id"], edge_label(dev.get("link", ""))))
    out.append("  " + legend_node(True))
    out.append("  { rank=same; %s; legend; }" % used_hosts[0])
    out.append("}")
    return "\n".join(out)


def interlock_dot(m):
    ilk = m.d["interlock"]
    out = [HEADER % ("1.2", FONT, FONT, FONT)]
    out.append('  label=<<B>Interlock system</B>: concept for discussion>;')
    colors = {"A": ("#FDEDEC", "#B03A2E"), "B": ("#FEF5E7", "#B9770E"), "C": ("#EBF5FB", "#2E86C1")}
    for layer in ilk["layers"]:
        fill, border = colors[layer["id"]]
        out.append('  layer%s [label=<<B>%s</B><BR/><FONT POINT-SIZE="9">%s</FONT><BR/><FONT POINT-SIZE="8" COLOR="#444444">%s</FONT>>, '
                   'style="filled", fillcolor="%s", color="%s", penwidth=2, margin="0.2,0.12"];'
                   % (layer["id"], esc(layer["name"]), esc(layer["tech"]), esc(_wrap(layer["text"], 52)).replace("\n", "<BR/>"), fill, border))
    for index, signal in enumerate(ilk["inputs"]):
        out.append('  in%d [label=%s, %s];' % (index, box_label(signal["name"], [signal.get("source", "")], signal["status"]), node_style(signal["status"])))
        out.append('  in%d -> layer%s;' % (index, signal["layer"]))
    for index, signal in enumerate(ilk["outputs"]):
        out.append('  out%d [label=%s, style="rounded,filled", fillcolor="#FFFFFF", color="%s"];'
                   % (index, box_label(signal["name"], ["acts on: " + signal.get("acts_on", "")]), colors[signal["layer"]][1]))
        out.append('  layer%s -> out%d [penwidth=1.5, color="%s"];' % (signal["layer"], index, colors[signal["layer"]][1]))
    out.append('  layerA -> layerB [label="safety chain open\\nremoves all permits", constraint=false, color="#B03A2E"];')
    out.append('  layerA -> layerC [style=dashed, taillabel="status (read only)", labeldistance=4.5, labelangle=-18, labelfontcolor="#2E86C1", constraint=false, color="#2E86C1"];')
    out.append('  layerB -> layerC [style=dashed, label="inputs, permits, first fault\\n(read only)", fontcolor="#2E86C1", color="#2E86C1"];')
    out.append('  layerC -> layerB [style=dashed, label="reset request", fontcolor="#2E86C1", color="#2E86C1", constraint=false];')
    out.append("  " + legend_node(False))
    out.append("}")
    return "\n".join(out)


def software_dot(m):
    sw = m.d["software"]
    out = [HEADER % ("0.9", FONT, FONT, FONT)]
    out.append('  label=<<B>Software architecture</B>: who talks to whom>;')
    out.append('  ca [label=<<B>Channel Access</B><BR/><FONT POINT-SIZE="9">all PVs, by name</FONT>>, style="filled", fillcolor="#EAECEE", color="#555555", height=2.6, width=1.5];')
    out.append('  hw [label=<<B>Devices</B><BR/><FONT POINT-SIZE="9">supplies, gauges, pumps,<BR/>valves, interlock PLC</FONT>>, style="rounded,filled", fillcolor="#FFFFFF", color="#555555"];')
    out.append('  cfg [label=<<B>controls.yaml</B><BR/><FONT POINT-SIZE="9">devices, PVs, tiers,<BR/>report groups</FONT>>, shape=note, style="filled", fillcolor="#FDFEFE", color="#555555"];')
    ids = set()
    for comp in sw["components"]:
        ids.add(comp["id"])
        out.append('  %s [label=%s, %s%s];' % (comp["id"], box_label(comp["name"], _wrap(comp.get("text", ""), 34).split("\n"), comp["status"]),
                                         node_style(comp["status"]), ", penwidth=2" if comp["id"] in ("iocs", "loops") else ""))
    flows = [("hw", "iocs", "serial, USB, Ethernet", "both", ""), ("iocs", "ca", "", "both", ""), ("loops", "ca", "reads and writes", "both", ""),
             ("ca", "gui", "show and command", "both", ""), ("ca", "archiver", "monitor", "forward", ""), ("ca", "report", "read once", "forward", ""),
             ("ca", "clients", "scan, tune", "both", ""), ("archiver", "gui", "history plots", "forward", "dashed"),
             ("archiver", "clients", "training data", "forward", "dashed"), ("gui", "report", "trigger", "forward", "dashed"),
             ("cfg", "gui", "pages", "forward", "dotted"), ("cfg", "archiver", "PV list, tiers", "forward", "dotted"), ("cfg", "report", "layout", "forward", "dotted")]
    fixed = ("hw", "ca", "cfg")
    for src, dst, label, direction, style in flows:
        if (src in ids or src in fixed) and (dst in ids or dst in fixed):
            out.append('  %s -> %s [label="%s", dir=%s%s%s];' % (src, dst, label, direction, ", style=%s" % style if style else "",
                                                                 ", constraint=false" if style == "dashed" else ""))
    out.append("  { rank=same; iocs; loops; }")
    out.append("  " + legend_node(False))
    out.append("}")
    return "\n".join(out)


def _short(text, width):
    return text if len(text) <= width else text[:width - 1].rstrip() + "\u2026"


def _wrap(text, width):
    words, lines, line = text.split(), [], ""
    for word in words:
        if len(line) + len(word) + 1 > width and line:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    lines.append(line)
    return "\n".join(lines)


def render(name, dot, out_dir):
    path = os.path.join(out_dir, name + ".dot")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(dot)
    for fmt, extra in (("svg", []), ("pdf", []), ("png", ["-Gdpi=170"])):
        subprocess.run(["dot", "-T" + fmt] + extra + [path, "-o", os.path.join(out_dir, name + "." + fmt)], check=True)
    return os.path.join(out_dir, name + ".png")


# ----------------------------------------------------------------------------- word document
def build_docx(m, images, out_path):
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(2.0))
    text_width = 17.0
    styles = doc.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(11)
    for name, size in (("Title", 24), ("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)):
        style = styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        style.element.rPr.rFonts.set(qn("w:asciiTheme"), "minorHAnsi")
        style.paragraph_format.space_before = Pt(14 if name != "Heading 3" else 10)
        style.paragraph_format.space_after = Pt(6)
        style.paragraph_format.keep_with_next = True

    def shade(cell, color):
        props = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), color.lstrip("#"))
        props.append(shd)

    def set_widths(tbl, widths):
        for index, width in enumerate(widths):
            tbl.columns[index].width = Cm(width)
        for row in tbl.rows:
            for index, width in enumerate(widths):
                row.cells[index].width = Cm(width)

    def write(cell, text, size=9, bold=False, mono=False, color=None, italic=False):
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(str(text))
        run.font.size = Pt(size)
        run.bold = bold
        run.italic = italic
        if mono:
            run.font.name = "Consolas"
        if color:
            run.font.color.rgb = RGBColor.from_string(color.lstrip("#"))
        return run

    def table(header, rows, widths, status_col=None, mono_col=None):
        tbl = doc.add_table(rows=1, cols=len(header))
        tbl.style = "Table Grid"
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False
        for index, text in enumerate(header):
            cell = tbl.rows[0].cells[index]
            shade(cell, "#D9E2F3")
            write(cell, text, bold=True)
        for row in rows:
            cells = tbl.add_row().cells
            for index, value in enumerate(row):
                if index == status_col and value in STATUS:
                    shade(cells[index], STATUS[value][1])
                    write(cells[index], STATUS[value][0], size=8, bold=True, color=STATUS[value][2])
                elif index == status_col and value == "proposed":
                    shade(cells[index], STATUS["new"][1])
                    write(cells[index], "PROPOSED", size=8, bold=True, color=STATUS["new"][2])
                elif index == status_col:
                    write(cells[index], str(value).upper(), size=8, bold=True, color="#555555")
                else:
                    write(cells[index], value, mono=(index == mono_col), size=8.5 if index == mono_col else 9)
        set_widths(tbl, widths)
        doc.add_paragraph().paragraph_format.space_after = Pt(2)
        return tbl

    def bullets(items):
        for item in items:
            paragraph = doc.add_paragraph(str(item), style="List Bullet")
            paragraph.paragraph_format.space_after = Pt(2)

    def para(text, italic=False, size=None, label=False):
        paragraph = doc.add_paragraph()
        run = paragraph.add_run(text)
        run.italic = italic
        run.bold = label
        if size:
            run.font.size = Pt(size)
        if label:
            paragraph.paragraph_format.keep_with_next = True
            paragraph.paragraph_format.space_after = Pt(2)
        return paragraph

    def picture(path, max_height=22.5):
        from PIL import Image
        with Image.open(path) as image:
            width_px, height_px = image.size
        width = text_width
        if width * height_px / width_px > max_height:
            width = max_height * width_px / height_px
        doc.add_picture(path, width=Cm(width))
        doc.paragraphs[-1].alignment = 1

    def page_break():
        doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    meta = m.d["meta"]
    doc.add_paragraph(meta["title"], style="Title")
    para(meta["subtitle"], size=13)
    para("Revision %s, %s. %s" % (meta["revision"], meta["date"], meta["author"]), size=10)
    para("This document is generated from controls.yaml. Change the YAML file and run build.py; do not edit the tables here by hand, the next build overwrites them.", italic=True, size=10)

    # 1 -----------------------------------------------------------------------------------
    doc.add_heading("1  Scope and status of this document", level=1)
    para("It lists every controlled device of the MIST-2 ion source, how it is connected, which process variables (PVs) exist today, "
         "which ones are proposed, and what changes for the rebuild at IBA. This revision is a baseline built from:")
    bullets(meta["basis"])
    para("Everything marked TBD or listed under open questions is a guess or a gap. PV names of existing devices come from the "
         "repository, not from the running IOCs, and still have to be checked against them.")
    for phase in m.d["phases"]:
        paragraph = doc.add_paragraph()
        paragraph.add_run(phase["name"] + ". ").bold = True
        paragraph.add_run(phase["text"])
    doc.add_heading("Status colors", level=2)
    table(["Status", "Meaning"], [[key, STATUS_TEXT[key]] for key in ("keep", "modify", "replace", "new", "later", "tbd")], [3.0, 14.0], status_col=0)

    # 2 -----------------------------------------------------------------------------------
    page_break()
    doc.add_heading("2  System overview", level=1)
    para("Devices by location, the computer that talks to each of them, and the physical link. The number of PVs is given as "
         "existing (+ proposed).")
    picture(images["overview"])

    doc.add_heading("2.1  Computers and IOCs", level=2)
    table(["Computer", "Location", "Role", "OS", "Uplink", "Status"],
          [[h["name"] + (" (%s)" % h["model"] if h.get("model") else ""), _loc(m, h["location"]), h.get("role", ""), h.get("os", ""), h.get("uplink", ""), h["status"]]
           for h in m.d["hosts"]], [3.0, 2.6, 4.2, 2.2, 3.2, 1.8], status_col=5)

    doc.add_heading("2.2  Changes at a glance", level=2)
    rows = []
    for dev in m.devices:
        if dev["status"] != "keep":
            rows.append([dev["name"], dev.get("model", ""), _change(dev), dev["status"]])
    table(["Device", "Model", "What changes", "Status"], rows, [4.0, 4.4, 6.8, 1.8], status_col=3)

    # 3 -----------------------------------------------------------------------------------
    page_break()
    doc.add_heading("3  Devices", level=1)
    para("One section per subsystem: a sketch with all PVs, then every device with its connection, its PVs, notes and open questions.")
    number = 0
    for sub in m.d["subsystems"]:
        if number:
            page_break()
        number += 1
        doc.add_heading("3.%d  %s" % (number, sub["name"]), level=2)
        para("Phase %s." % sub["phase"], italic=True, size=10)
        picture(images["sub_" + sub["id"]], max_height=20.0)
        for dev in [d for d in m.devices if d["subsystem"] == sub["id"]]:
            doc.add_heading("%s" % dev["name"], level=3)
            existing, proposed = m.counts(dev)
            host = m.hosts[dev["host"]]
            link = dev.get("link", "")
            if dev.get("via"):
                adapter = m.adapters[dev["via"]]
                link = "%s, via %s (%s)" % (link, adapter["name"], adapter.get("link", ""))
            attributes = [["Model", dev.get("model", "")], ["Location", _loc(m, dev["location"])], ["Controlled by", host["name"]],
                          ["Connection", link], ["Protocol / support", dev.get("protocol", "")]]
            if loads_of(dev):
                attributes.append(["EPICS databases", "\n".join("%s (%s)" % (load["db"], fmt_macros(m.macros(load)))
                                                             for load in loads_of(dev))])
            for flag, text in (dev.get("flags") or {}).items():
                attributes.append([FLAGS.get(flag, flag), text])
            attributes.append(["Status", dev["status"]])
            tbl = doc.add_table(rows=0, cols=2)
            tbl.style = "Table Grid"
            tbl.autofit = False
            for key, value in attributes:
                cells = tbl.add_row().cells
                shade(cells[0], "#F2F2F2")
                write(cells[0], key, bold=True)
                if key == "Status":
                    shade(cells[1], STATUS[value][1])
                    write(cells[1], "%s: %s" % (STATUS[value][0], STATUS_TEXT[value]), bold=True, color=STATUS[value][2])
                else:
                    write(cells[1], value)
            set_widths(tbl, [3.6, 13.4])
            doc.add_paragraph().paragraph_format.space_after = Pt(2)

            if dev.get("pvs_unknown"):
                para("Existing PVs: not in the repository. They have to come from the running IOC (dbl).", italic=True, size=10)
            if m.public(dev):
                rows = []
                for pv in m.public(dev):
                    state = {"existing": "exists", "reuse": "reuse", "proposed": "proposed"}[pv["state"]]
                    if dev["status"] == "replace":
                        state = "goes away"
                    description = pv["desc"] + (" (%s)" % pv["remark"] if pv.get("remark") else "")
                    if pv.get("aliases"):
                        description += " (alias: %s)" % ", ".join(pv["aliases"])
                    rows.append([pv["name"], pv["type"], "W" if pv["type"] in WRITE_TYPES else "R", pv["egu"], description, state])
                table(["PV", "Record", "R/W", "Unit", "Description", "State"], rows, [5.6, 1.5, 1.0, 1.2, 5.9, 1.8], status_col=5, mono_col=0)
            elif not dev.get("pvs_unknown"):
                para("No PVs yet.", italic=True, size=10)
            if dev.get("options"):
                para("Options", size=10, label=True)
                table(["Option", "What it is", "Interface", "Comment"],
                      [[o["name"], o.get("text", ""), o.get("interface", ""), o.get("note", "")] for o in dev["options"]], [4.0, 5.6, 2.4, 5.0])
            if dev.get("notes"):
                para("Notes", size=10, label=True)
                bullets(dev["notes"])
            if dev.get("questions"):
                para("Open questions", size=10, label=True)
                bullets(dev["questions"])

    # 4 -----------------------------------------------------------------------------------
    page_break()
    ilk = m.d["interlock"]
    doc.add_heading("4  Interlock system", level=1)
    for text in ilk["intro"]:
        para(text)
    picture(images["interlock"], max_height=17.0)
    doc.add_heading("4.1  Layers", level=2)
    table(["Layer", "Technology", "What it does"], [[l["name"], l["tech"], l["text"]] for l in ilk["layers"]], [4.0, 5.0, 8.0])
    doc.add_heading("4.2  Inputs (to be completed)", level=2)
    table(["Signal", "Layer", "Source", "Status"], [[s["name"], s["layer"], s.get("source", ""), s["status"]] for s in ilk["inputs"]], [6.0, 1.4, 7.8, 1.8], status_col=3)
    doc.add_heading("4.3  Outputs (to be completed)", level=2)
    table(["Output", "Layer", "Acts on"], [[s["name"], s["layer"], s.get("acts_on", "")] for s in ilk["outputs"]], [6.0, 1.4, 9.6])
    doc.add_heading("4.4  Design rules", level=2)
    bullets(ilk["rules"])

    # 5 -----------------------------------------------------------------------------------
    page_break()
    sw = m.d["software"]
    doc.add_heading("5  Operator interface, logging, reports and control loops", level=1)
    for text in sw["intro"]:
        para(text)
    picture(images["software"], max_height=13.0)
    table(["Component", "What it does", "Status"], [[c["name"], c.get("text", ""), c["status"]] for c in sw["components"]], [4.0, 11.2, 1.8], status_col=2)
    doc.add_heading("5.1  GUI", level=2)
    bullets(sw["gui"])
    doc.add_heading("5.2  Snapshot report (printout)", level=2)
    bullets(sw["report"])
    doc.add_heading("5.3  Data logging", level=2)
    table(["Tier", "What is stored", "Kept for", "Used for"], [[t["tier"], t["rate"], t["keep"], t["use"]] for t in sw["tiers"]], [2.4, 4.6, 2.4, 7.6])
    bullets(sw["archiver"])
    doc.add_heading("5.4  Control loops", level=2)
    bullets(sw["loops"])

    # 6 -----------------------------------------------------------------------------------
    page_break()
    doc.add_heading("6  Work packages", level=1)
    for wp in m.d["work_packages"]:
        doc.add_heading("%s  %s (phase %s)" % (wp["id"], wp["name"], wp["phase"]), level=3)
        bullets(wp["items"])

    doc.add_heading("7  PV naming", level=1)
    for text in m.d["naming"]["text"]:
        para(text)

    # 7 -----------------------------------------------------------------------------------
    page_break()
    doc.add_heading("8  Open questions", level=1)
    para("Collected from all chapters. Answers go into controls.yaml, then the question is deleted there.")
    rows, count = [], 0
    for text in m.d.get("global_questions", []):
        count += 1
        rows.append([str(count), "General", text, ""])
    for host in m.d["hosts"]:
        for text in host.get("questions", []):
            count += 1
            rows.append([str(count), host["name"], text, ""])
    for dev in m.devices:
        for text in dev.get("questions", []):
            count += 1
            rows.append([str(count), dev["name"], text, ""])
    for text in ilk.get("questions", []):
        count += 1
        rows.append([str(count), "Interlock system", text, ""])
    for text in sw.get("questions", []):
        count += 1
        rows.append([str(count), "GUI, logging, loops", text, ""])
    table(["#", "Topic", "Question", "Answer"], rows, [0.8, 3.6, 8.0, 4.6])

    doc.add_heading("9  How this document is built", level=1)
    bullets(["controls.yaml holds devices, connections, status, proposed PVs, questions and work packages.",
             "Existing PVs are read from the EPICS databases in EPICS/Db, with the macros of the dbLoadRecords lines of the "
             "two st.cmd files. build.py warns about every difference between those lines and controls.yaml.",
             "Internal records (fan-outs, arrays, helper records) are not listed. The registry for the GUI and the tests "
             "(plan/registry.py) lists them with every role.",
             "build.py writes the sketches (SVG, PDF, PNG, drawn by Graphviz) and this document.",
             "Keep the three in one git repository. Every decision is then one small, reviewable change to the YAML file."])
    doc.save(out_path)


def _loc(m, loc_id):
    for loc in m.d["locations"]:
        if loc["id"] == loc_id:
            return loc["name"]
    return loc_id


def _change(dev):
    if dev.get("change"):
        return dev["change"]
    if dev["status"] == "new":
        return "Add to the control system"
    if dev["status"] == "replace":
        return "Remove"
    if dev["status"] == "later":
        return "Move into EPICS in phase 2"
    if dev["status"] == "tbd":
        return (dev.get("questions") or ["Open"])[0]
    parts = []
    if dev.get("libcom1"):
        parts.append("libcom1 protocol 2 firmware, identity PVs")
    if "Ethernet proposed" in dev.get("link", ""):
        parts.append("USB to Ethernet")
    return ", ".join(parts) or (dev.get("notes") or [""])[0]


def fix_zip_dates(path, date):
    """Rewrite a zip file (the docx) with every entry dated to the plan revision, so that the same
    inputs give the same bytes."""
    stamp = tuple(int(x) for x in str(date).split("-")) + (0, 0, 0)
    with zipfile.ZipFile(path) as old:
        entries = [(info, old.read(info.filename)) for info in old.infolist()]
    with zipfile.ZipFile(path, "w") as new:
        for info, data in entries:
            fixed = zipfile.ZipInfo(info.filename, date_time=stamp)
            fixed.compress_type, fixed.external_attr = info.compress_type, info.external_attr
            new.writestr(fixed, data)


# ----------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yaml", default=os.path.join(HERE, "controls.yaml"))
    parser.add_argument("--db-dir", default=os.path.join(REPO, "EPICS", "Db"))
    parser.add_argument("--out", default=os.path.join(HERE, "out"))
    parser.add_argument("--no-docx", action="store_true")
    args = parser.parse_args()
    if not shutil.which("dot"):
        sys.exit("Graphviz not found: install it (apt install graphviz / winget install Graphviz.Graphviz) and put 'dot' on the PATH")
    os.makedirs(args.out, exist_ok=True)
    m = Model(args.yaml, args.db_dir)
    images = {"overview": render("overview", overview_dot(m), args.out)}
    for sub in m.d["subsystems"]:
        images["sub_" + sub["id"]] = render("sub_" + sub["id"], subsystem_dot(m, sub), args.out)
    images["interlock"] = render("interlock", interlock_dot(m), args.out)
    images["software"] = render("software", software_dot(m), args.out)
    if shutil.which("pdfunite"):
        pdfs = [os.path.join(args.out, os.path.basename(p)[:-4] + ".pdf") for p in images.values()]
        subprocess.run(["pdfunite"] + pdfs + [os.path.join(args.out, "MIST-2_Control_System_Sketches.pdf")], check=False)
    if not args.no_docx:
        build_docx(m, images, os.path.join(args.out, "MIST-2_Control_System_Plan.docx"))
        fix_zip_dates(os.path.join(args.out, "MIST-2_Control_System_Plan.docx"), m.d["meta"]["date"])
    devices = len(m.devices)
    existing = sum(1 for dev in m.devices for pv in m.public(dev) if pv["state"] == "existing")
    proposed = sum(m.counts(dev)[1] for dev in m.devices)
    print("%d devices, %d existing PVs, %d proposed PVs, %d sketches" % (devices, existing, proposed, len(images)))
    for warning in m.warnings:
        print("WARNING:", warning)


if __name__ == "__main__":
    main()
