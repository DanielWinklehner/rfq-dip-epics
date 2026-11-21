import React from "react";
import Stack from "@mui/material/Stack";
import Channels from "./Channels";
import RoleGrid from "./RoleGrid";

// One value per device or per channel, with the channel's fault where the
// device reports one. Unit and format come from the record.
const Reading = ({ id }) => (
  <Stack spacing={2}>
    <RoleGrid id={id} rows={[["value"]]} />
    <Channels id={id} rows={[["value", "fault"]]} />
  </Stack>
);

export default Reading;
