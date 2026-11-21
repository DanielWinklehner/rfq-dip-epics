import React from "react";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { channelLabel, channelsOf } from "../../registry";
import RoleGrid from "./RoleGrid";

// The channels of a device, each with its label from the registry (or its id
// when the registry has none) above a grid of its roles.
const Channels = ({ id, rows, unlabelled = (channel) => channel }) => (
  <Stack spacing={1.5}>
    {channelsOf(id).map((channel) => (
      <Stack key={channel} spacing={1} data-channel={channel}>
        <Typography variant="subtitle2">
          {channelLabel(id, channel) ?? unlabelled(channel)}
        </Typography>
        <RoleGrid id={id} channel={channel} rows={rows} />
      </Stack>
    ))}
  </Stack>
);

export default Channels;
