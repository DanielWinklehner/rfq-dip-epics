import React from "react";
import RoleGrid from "./RoleGrid";

// Run request and run contact, the three status contacts and the state made
// from them, speed and current from the RS-232 record and that record's age.
// A pump of the TIC station (a channel of class turbo, T32) has the request,
// the state of the station as its read-back, the state's word, the speed and at speed
// where it has them, and what became of the last request (a refusal's word).
const rows = [
  ["run_cmd", "run_state"],
  ["accel", "atspeed"],
  ["failure", "state"],
  ["speed", "current"],
  ["age"],
  ["result"],
];

const Turbo = ({ id, channel }) => <RoleGrid id={id} channel={channel} rows={rows} />;

export default Turbo;
