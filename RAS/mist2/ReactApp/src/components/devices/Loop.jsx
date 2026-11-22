import React from "react";
import Stack from "@mui/material/Stack";
import RoleGrid from "./RoleGrid";

// A control loop (docs/emulation/LOOP.md), in the order the operator needs it:
// the mode request beside the mode, and right below it why the loop last
// handed back or refused (a refused request returns to MANUAL within a cycle,
// so the word is where the eye already is); the set point beside the measured
// value, the output beside the error, the limit flag, the service, the permits.
const operation = [
  ["mode_cmd", "mode"],
  ["reason", null],
  ["sp_cmd", "pv"],
  ["out", "error"],
  ["limit", "service"],
  ["permit1", "permit2"],
  ["permit3", null],
];

// What tuning needs besides the trend: the three terms of the output.
const terms = [
  ["pterm", "iterm"],
  ["dterm", null],
];

// The settings, saved by autosave in the IOC (LOOP.md section 5).
const settings = [
  ["kp", "ki"],
  ["kd", "dfilter"],
  ["outmin", "outmax"],
  ["slew", null],
  ["spmin", "spmax"],
  ["stale", "watchdog"],
];

const Loop = ({ id }) => (
  <Stack spacing={2}>
    <RoleGrid id={id} rows={operation} />
    <RoleGrid id={id} rows={terms} title="Terms of the output" />
    <RoleGrid id={id} rows={settings} title="Settings, saved by the IOC" />
  </Stack>
);

export default Loop;
