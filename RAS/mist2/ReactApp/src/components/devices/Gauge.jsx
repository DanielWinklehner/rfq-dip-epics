import React from "react";
import Stack from "@mui/material/Stack";
import Channels from "./Channels";
import RoleGrid from "./RoleGrid";

// Pressure and the gauge enable where the gauge has one; a controller with
// several gauges shows each channel with its label. A gauge the TIC switches
// (T32) shows its switch beside the pressure, the station's state beside it, what
// became of the last request, and whether the TIC switches it by itself (its
// slave setup) with the set point.
const channelRows = [
  ["p", "enable"],
  ["state", "enable_state"],
  ["result"],
  ["slave", "slave_on"],
];

const Gauge = ({ id }) => (
  <Stack spacing={2}>
    <RoleGrid id={id} rows={[["p", "enable"]]} />
    <Channels id={id} rows={channelRows} />
  </Stack>
);

export default Gauge;
