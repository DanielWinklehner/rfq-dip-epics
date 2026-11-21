import React from "react";
import Stack from "@mui/material/Stack";
import Channels from "./Channels";
import RoleGrid from "./RoleGrid";

const exponent = { p: { exponent: true } };

// Pressure in exponent format and the gauge enable where the gauge has one;
// a controller with several gauges shows each channel with its label.
const Gauge = ({ id }) => (
  <Stack spacing={2}>
    <RoleGrid id={id} rows={[["p", "enable"]]} fieldProps={exponent} />
    <Channels id={id} rows={[["p"]]} fieldProps={exponent} />
  </Stack>
);

export default Gauge;
