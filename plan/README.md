# MIST-2 control system plan

One data file, one script, everything else is generated.

| File | What it is |
|---|---|
| `controls.yaml` | The single source of truth: computers, devices, connections, status, proposed PVs, interlock concept, work packages, open questions |
| `epics_db/` | Snapshot of the EPICS databases from `rfq-dip-epics` (commit in `SOURCE_COMMIT`). Existing PVs are read from here |
| `build.py` | Reads both and writes everything in `out/` |
| `out/*.svg, *.pdf, *.png` | Sketches: overview, one per subsystem, interlock concept (drawn by Graphviz) |
| `out/MIST-2_Control_System_Plan.docx` | The same information as a Word document, device by device |
| `CO-U32_driver_brief.md` | Kickoff brief for the Linux/Windows CO-U32 driver project |

## Build

```
pip install pyyaml python-docx pillow
# Graphviz: apt install graphviz   |   winget install Graphviz.Graphviz   |   conda install graphviz
python build.py
```

`python build.py --db-dir ../rfq-dip-epics/EPICS/Db` reads the live databases instead of the snapshot.
`python build.py --no-docx` only redraws the sketches.

## How to iterate

1. Change `controls.yaml`: set a `status`, fill in a `model`, add a device, add or delete a `proposed` PV, delete a question once it is answered.
2. Run `python build.py`. It warns about unknown hosts, adapters, status values and duplicate PV names.
3. Commit the YAML change. The git history is then the decision log.

Status values: `keep`, `modify`, `replace`, `new`, `later` (phase 2), `tbd`.

Do not edit the Word document by hand. The next build overwrites it.

## Known limits of this baseline

- Existing PVs come from the repository, not from the running IOCs. Compare with `dbl` from both IOCs.
- Devices whose PVs are not in the repository (Optas, mass flow controller, HV supplies 3 and 4) show "PVs: ?".
- Everything proposed (PV names of new devices, the interlock concept) is a starting point for discussion.
