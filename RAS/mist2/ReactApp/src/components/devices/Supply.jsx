import React from "react";
import Stack from "@mui/material/Stack";
import RoleGrid from "./RoleGrid";

// What the operator works with: set points beside their echo (the filament heating supply's
// current is a set point), the read-backs, the output request beside the
// output state, power and the remote/local status.
const operation = [
  ["vset", "vget"],
  ["iset", null],
  ["vread", "iread"],
  ["out_cmd", "out_state"],
  ["power", "status"],
  ["mode", "fault"],
];

// A setting below that: the current limit of a Matsusada supply beside the
// limit the supply reports. The IOC saves every change and sends it with every
// switch-on (STATUS.md, owner's answer 10).
const settings = [["ilimit", "ilimit_get"]];

const Supply = ({ id }) => (
  <Stack spacing={2}>
    <RoleGrid id={id} rows={operation} />
    <RoleGrid id={id} rows={settings} title="Setting, saved by the IOC" />
  </Stack>
);

export default Supply;
