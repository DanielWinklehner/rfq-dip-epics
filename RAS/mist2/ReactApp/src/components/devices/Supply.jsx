import React from "react";
import RoleGrid from "./RoleGrid";

// Pairs side by side: a set point with its echo, the read-backs, the output
// request with the output state (STATUS.md P10, P17). A current that is a
// limit (ilimit) and one that is a set point (iset) are told apart by role.
const rows = [
  ["vset", "vget"],
  ["iset", "iget"],
  ["ilimit", "ilimit_get"],
  ["vread", "iread"],
  ["out_cmd", "out_state"],
  ["power", "status"],
  ["mode", "fault"],
];

const Supply = ({ id }) => <RoleGrid id={id} rows={rows} />;

export default Supply;
