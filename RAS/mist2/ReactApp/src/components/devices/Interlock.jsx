import React from "react";
import Stack from "@mui/material/Stack";
import Channels from "./Channels";
import RoleGrid from "./RoleGrid";

// The role "open" is 1 while an interlock is open: its record has no state
// strings, so the words of the role are given here.
export const openWords = { lamp: true, custom_selection_strings: ["closed", "OPEN"] };

const Interlock = ({ id }) => (
  <Stack spacing={2}>
    <RoleGrid id={id} rows={[["open"]]} fieldProps={{ open: openWords }} />
    <Channels id={id} rows={[["state"]]} />
  </Stack>
);

export default Interlock;
