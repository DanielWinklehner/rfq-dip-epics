# Lab snapshot of 2023 (`latest.zip`)

Unchanged copy of `latest.zip` (files dated February 2022 to June 2023): the databases, protocol
files, `st.cmd` and GUI pages of the rack IOC as they were in the lab at that time.

**Read-only reference. Nothing here is loaded by an IOC or built into the GUI.**

Why it is here:

- It is newer than `master` for the power supplies (`matsusada_au20p7.db`, `rek.db`, `tdk.db`) and
  it holds the only copy of the mass flow controller files (`IOC.mfc.db`, `mfc.proto`).
- Its PV names are the best available record of what lab clients use. They differ from the
  repository in places, see `docs/emulation/DESIGN.md`.
- The files were changed further in the lab after this snapshot, without a backup. The current
  lab files and `dbl` output replace this folder once they are available.
