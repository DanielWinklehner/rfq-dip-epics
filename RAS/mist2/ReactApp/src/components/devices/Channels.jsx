import React from "react";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { channelLabel, channelsOf, isSpare } from "../../registry";
import RoleGrid from "./RoleGrid";

// The channels of a device, each with its label from the registry (or its id
// when the registry has none, marked when it is spare) above its roles.
const Channels = ({ id, rows }) => (
  <Stack spacing={1.5}>
    {channelsOf(id).map((channel) => (
      <Stack key={channel} spacing={1} data-channel={channel}>
        <Typography variant="subtitle2">
          {channelLabel(id, channel) ?? channel}
          {isSpare(id, channel) && " · spare, not connected"}
        </Typography>
        <RoleGrid id={id} channel={channel} rows={rows} />
      </Stack>
    ))}
  </Stack>
);

export default Channels;
