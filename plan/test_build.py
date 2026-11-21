"""Tests of the database parser of plan/build.py (standard library only).

    python3 -m unittest plan/test_build.py        (from the repository root)
"""
import glob
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import REPO, DbError, fault_analysis, parse_db, simple_record_names  # noqa: E402


def parse(text, macros=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.db")
        with open(path, "w") as handle:
            handle.write(text)
        return parse_db(path, macros or {})


class ParseDb(unittest.TestCase):
    def test_body_on_one_line(self):
        recs = parse('record(ai, "$(DEVICE):extra:get") { field(DESC, "x") }\n', {"DEVICE": "AIM"})
        self.assertEqual([(r["name"], r["key"], r["desc"]) for r in recs], [("AIM:extra:get", "extra:get", "x")])

    def test_two_records_on_one_line_and_no_trailing_newline(self):
        recs = parse('record(ai,"a"){field(EGU,"V")} record(bo, "b") {}')
        self.assertEqual([(r["name"], r["type"], r["egu"]) for r in recs], [("a", "ai", "V"), ("b", "bo", "")])

    def test_opening_brace_on_the_next_line(self):
        recs = parse('record(ai, "a")\n{\n    field(SCAN, "1 second")\n}\n')
        self.assertEqual(recs[0]["scan"], "1 second")

    def test_record_without_body_and_grecord(self):
        recs = parse('record(ai, "a")\ngrecord(ao, "b") { field(DRVH, "5") }\n')
        self.assertEqual([r["name"] for r in recs], ["a", "b"])
        self.assertEqual(recs[1]["fields"]["DRVH"], "5")

    def test_unquoted_names_and_values(self):
        recs = parse('record(calc, $(P):heartbeat) {\n field(SCAN, Passive)\n field(INPA, $(P):x)\n}\n', {"P": "IOC"})
        self.assertEqual(recs[0]["name"], "IOC:heartbeat")
        self.assertEqual(recs[0]["scan"], "Passive")
        self.assertEqual(recs[0]["fields"]["INPA"], "IOC:x")
        with self.assertRaisesRegex(DbError, "expected \\), found 'NPP'"):  # as in EPICS: needs quotes
            parse('record(calc, "a") { field(INPA, b NPP) }\n')

    def test_comments_at_the_end_of_a_line_and_on_their_own(self):
        recs = parse('# record(ai, "commented")\nrecord(ao, "a") {  # opening\n'
                     '    field(DRVH, "100")   # drive high limit\n} # closing\n')
        self.assertEqual([r["name"] for r in recs], ["a"])
        self.assertEqual(recs[0]["fields"]["DRVH"], "100")

    def test_hash_inside_a_quoted_string(self):
        recs = parse('record(bo, "AU:alloff:chain1") { field(DESC, "#AL SW0 on $(PORT1=mat_opt)") }\n')
        self.assertEqual(recs[0]["desc"], "#AL SW0 on mat_opt")

    def test_info_entries(self):
        recs = parse('record(ai, "a") {\n info(autosaveFields, "VAL")\n field(EGU, "A")\n}\n')
        self.assertEqual(recs[0]["info"], {"autosaveFields": "VAL"})
        self.assertEqual(recs[0]["egu"], "A")

    def test_alias_inside_a_body_and_as_a_statement(self):
        recs = parse('record(ai, "$(D):new") { alias("$(D):old") }\nalias("$(D):new", "$(D):older")\n', {"D": "X"})
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["aliases"], ["X:old", "X:older"])

    def test_alias_of_an_unknown_record(self):
        with self.assertRaisesRegex(DbError, "test.db line 1: alias b for record a"):
            parse('alias("a", "b")\n')

    def test_statement_not_understood(self):
        with self.assertRaisesRegex(DbError, "test.db line 2: statement 'include'"):
            parse('record(ai, "a")\ninclude "other.db"\n')

    def test_body_item_not_understood(self):
        with self.assertRaisesRegex(DbError, "'fild' in the body of record a"):
            parse('record(ai, "a") { fild(DESC, "x") }\n')

    def test_unclosed_body_and_string(self):
        with self.assertRaisesRegex(DbError, "unexpected end of file"):
            parse('record(ai, "a") { field(DESC, "x")\n')
        with self.assertRaisesRegex(DbError, "closing quote"):
            parse('record(ai, "a") { field(DESC, "x) }\n')

    def test_guard_fires_when_the_scan_finds_more(self):
        # The plain scan cannot tell a record statement inside a string from a real one, so this
        # file makes it disagree with the parser: the guard must fail and name the record.
        with self.assertRaisesRegex(DbError, "scan finds 2 record statements, the parser 1. Missed: b"):
            parse('record(ai, "a") { field(DESC, "copy of record(ai, b)") }\n')


def faults(text, statements=None):
    """fault_analysis over an inline database; the device behind a StreamDevice record is its port."""
    records = {}
    for rec in parse(text):
        link = rec["fields"].get("INP") or rec["fields"].get("OUT") or ""
        records[rec["name"]] = dict(rec, source=link.split()[-1] if rec["fields"].get("DTYP") == "stream" else None)
    result, missing, needless = fault_analysis(records, statements or {})
    return ({n: (sorted(result["silent"][n]), sorted(result["closed"][n])) for n in records}, missing, needless)


DEV = 'field(DTYP, "stream") field(INP, "@x.proto get P1")'
BOTH, CLOSED, NONE = (["P1"], ["P1"]), ([], ["P1"]), ([], [])


class FaultRule(unittest.TestCase):
    def test_scanned_device_record(self):
        got, missing, _ = faults('record(ai, "a") { %s field(SCAN, "1 second") }' % DEV)
        self.assertEqual((got["a"], missing), (BOTH, []))

    def test_forward_link_and_MS(self):
        got, _, _ = faults('record(ai, "a") { %s field(SCAN, "1 second") field(FLNK, "b") }\n'
                           'record(calc, "b") { field(INPA, "a NPP MS") field(FLNK, "c") }\n'
                           'record(calc, "c") { field(INPA, "a NPP") }' % DEV)
        self.assertEqual((got["b"], got["c"]), (BOTH, NONE))      # without MS no severity

    def test_once_at_start_is_not_processed(self):
        got, _, _ = faults('record(ai, "a") { %s field(SCAN, "1 second") }\n'
                           'record(seq, "init") { field(PINI, "YES") field(DOL1, "a NPP MS") field(LNK1, "x PP") }' % DEV)
        self.assertEqual(got["init"], NONE)

    def test_passive_device_record_nothing_processes(self):
        got, _, _ = faults('record(ai, "a") { %s field(PINI, "YES") }' % DEV)
        self.assertEqual(got["a"], NONE)

    def test_io_intr_only_when_closed(self):
        got, _, _ = faults('record(ai, "raw") { %s field(SCAN, "I/O Intr") }\n'
                           'record(ai, "pub") { field(INP, "raw NPP MS") field(SCAN, "1 second") }' % DEV)
        self.assertEqual((got["raw"], got["pub"]), (CLOSED, CLOSED))

    def test_cp_input_link_processes(self):
        got, _, _ = faults('record(aai, "data") { %s field(SCAN, ".5 second") }\n'
                           'record(bi, "b") { field(INP, "data.VAL[0] CP MS") }' % DEV.replace("get P1", "all P1"))
        self.assertEqual(got["b"], BOTH)

    WRITER = ('record(calcout, "tick") { field(SCAN, ".1 second") field(OOPT, "When Non-zero") '
              'field(OUT, "rd.PROC PP") }\nrecord(ai, "rd") { %s }' % DEV)

    def test_writer_to_a_device_record_needs_a_statement(self):
        _, missing, _ = faults(self.WRITER)
        self.assertEqual(missing, ["tick"])

    def test_writer_stated_closed_processes_its_target(self):
        got, missing, _ = faults(self.WRITER, {"tick": ["closed"]})
        self.assertEqual((got["tick"], got["rd"], missing), (CLOSED, BOTH, []))

    def test_writer_stated_never_processes_nothing(self):
        got, _, _ = faults(self.WRITER, {"tick": []})
        self.assertEqual((got["tick"], got["rd"]), (NONE, NONE))

    def test_disabled_with_severity_needs_a_statement(self):
        text = ('record(ai, "raw") { %s field(SCAN, "I/O Intr") }\n'
                'record(ai, "pub") { field(INP, "raw NPP MS") field(SCAN, "1 second") '
                'field(SDIS, "stale NPP") field(DISS, "INVALID") }\nrecord(calc, "stale") { }' % DEV)
        self.assertEqual(faults(text)[1], ["pub"])
        got, missing, _ = faults(text, {"pub": ["silent", "closed"]})
        self.assertEqual((got["pub"], missing), (BOTH, []))

    def test_needless_statement(self):
        _, _, needless = faults('record(ai, "a") { %s field(SCAN, "1 second") }' % DEV, {"a": ["silent"]})
        self.assertEqual(needless, ["a"])


class EveryDatabase(unittest.TestCase):
    def test_every_file_in_EPICS_Db(self):
        files = sorted(glob.glob(os.path.join(REPO, "EPICS", "Db", "*.db")))
        self.assertTrue(files)
        for path in files:
            with self.subTest(db=os.path.basename(path)):
                with open(path, errors="replace") as handle:
                    scanned = simple_record_names(handle.read())
                records = parse_db(path, {})
                self.assertEqual(len(records), len(scanned))
                self.assertGreater(len(records), 0)


if __name__ == "__main__":
    unittest.main()
