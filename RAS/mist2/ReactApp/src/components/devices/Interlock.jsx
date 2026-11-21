import React from "react";
import Stack from "@mui/material/Stack";
import Channels from "./Channels";
import RoleGrid from "./RoleGrid";

// The summary and the state of each input.
const Interlock = ({ id }) => (
  <Stack spacing={2}>
    <RoleGrid id={id} rows={[["open"]]} />
    <Channels id={id} rows={[["state"]]} />
  </Stack>
);

export default Interlock;
