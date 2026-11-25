import React from "react";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { channelFlags, channelLabel, channelsOf, isChannelInstalled, isSpare } from "../../registry";
import RoleGrid from "./RoleGrid";

// The channels of a device, each with its label from the registry (or its id
// when the registry has none, marked when it is spare) above its roles. A
// channel flagged not installed shows its label and the reason only, as a
// device that is not installed is not drawn.
const Channels = ({ id, rows }) => (
  <Stack spacing={1.5}>
    {channelsOf(id).map((channel) => (
      <Stack key={channel} spacing={1} data-channel={channel}>
        <Typography variant="subtitle2">
          {channelLabel(id, channel) ?? channel}
          {isSpare(id, channel) && " · spare, not connected"}
          {!isChannelInstalled(id, channel) && ` · not installed: ${channelFlags(id, channel).not_installed}`}
        </Typography>
        {isChannelInstalled(id, channel) && <RoleGrid id={id} channel={channel} rows={rows} />}
      </Stack>
    ))}
  </Stack>
);

export default Channels;
