import React from "react";
import RoleGrid from "./RoleGrid";

// The data logger's state as its records in the rack IOC give it
// (docs/emulation/LOGGER.md section 6): alive and the database first, then
// what it logs, how fast, and what it had to hold back or lose.
const rows = [
  ["alive", "db"],
  ["connected", "disconnected"],
  ["rows", "buffer"],
  ["dropped", "count"],
];

const Logger = ({ id }) => <RoleGrid id={id} rows={rows} />;

export default Logger;
