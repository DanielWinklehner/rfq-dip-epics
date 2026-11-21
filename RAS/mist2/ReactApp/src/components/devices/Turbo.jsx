import React from "react";
import RoleGrid from "./RoleGrid";

// Run request and run contact, the three status contacts and the state made
// from them, speed and current from the RS-232 record and that record's age.
const rows = [
  ["run_cmd", "run_state"],
  ["accel", "atspeed"],
  ["failure", "state"],
  ["speed", "current"],
  ["age"],
];

const Turbo = ({ id }) => <RoleGrid id={id} rows={rows} />;

export default Turbo;
