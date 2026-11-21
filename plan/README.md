# MIST-2 control system plan

One data file, two scripts, everything else is generated.

| File | What it is |
|---|---|
| `controls.yaml` | The single source of truth: computers, devices, connections, status, database loads, proposed PVs, roles of the records, interlock concept, work packages, open questions |
| `build.py` | Reads the YAML, the databases in `EPICS/Db` and the two `st.cmd` files, checks that they agree, and writes everything in `out/` |
| `registry.py` | Writes the device registry of the GUI and the tests, `RAS/mist2/ReactApp/src/registry/registry.json` (same check as `build.py`) |
| `out/*.pdf` | Sketches: overview, one per subsystem, interlock concept (drawn by Graphviz). PNG, SVG and DOT files are written next to them but not tracked |
| `out/MIST-2_Control_System_Plan.docx` | The same information as a Word document, device by device |
| `CO-U32_driver_brief.md` | Kickoff brief for the Linux/Windows CO-U32 driver project |

## Build

From the repository root, in the tools container (Graphviz and python-docx live there):

```
make -C emulation plan-check   # build into a temporary directory, fail on any warning
make -C emulation plan         # regenerate plan/out
make -C emulation registry     # regenerate the registry
```

Without the container: `pip install pyyaml python-docx pillow`, Graphviz on the PATH, then
`python plan/build.py` (`--no-docx` only redraws the sketches, `--db-dir DIR` reads other
databases). `python plan/registry.py` needs only PyYAML.

## How the plan matches what was built

- A device (or a host, for the records of the IOC itself) has `epics:` with one database load
  `{db, macros}` or a list of them. Its existing PVs are read from those databases.
- Each host names its `st_cmd`. `build.py` compares every load in the YAML with the
  `dbLoadRecords` lines of the `st.cmd` files, in both directions: a line no device claims, a load
  no `st.cmd` has, different macros, a device on the wrong IOC. Each difference is a `WARNING`
  that names the device and the file.
- The section `databases:` gives every record of every loaded database a role (what the GUI and
  the tests ask for: `vset`, `state`, ...) or marks it `internal`. A record without either is a
  warning, so a record added to a database later cannot be forgotten in the registry.
- `registry.py` refuses to write while there is any warning.

## How to iterate

1. Change `controls.yaml`: set a `status`, fill in a `model`, add a device, add or delete a `proposed` PV, delete a question once it is answered.
2. Run `make -C emulation plan-check`. It warns about unknown hosts, adapters, status values, duplicate PV names and every disagreement with the databases and the `st.cmd` files.
3. Run `make -C emulation plan registry` and commit the YAML change with the generated files. The git history is then the decision log.

Status values: `keep`, `modify`, `replace`, `new`, `later` (phase 2), `tbd`.
Device flags (shown by the GUI): `not_polled`, `assumed`, each with a reason.

Do not edit the Word document or the registry by hand. The next build overwrites them.

## Known limits

- Existing PVs come from the repository, not from the running lab IOCs. The names are those of
  the lab's IOC of 2023 (decision D1); compare with `dbl` from both lab IOCs when the lab files
  arrive.
- Devices without a database (flow Opta, roughing pumps, the new gauge controller and interlock)
  show "PVs: ?" or only proposed PVs.
- Everything proposed (PV names of new devices, the interlock concept) is a starting point for discussion.
