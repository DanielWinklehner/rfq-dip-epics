import React from "react";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { channelClass, channelFlags, channelLabel, channelsOf, isChannelInstalled, isSpare } from "../../registry";
import RoleGrid from "./RoleGrid";
import { widgetOf } from "./index";

// The channels of a device, each with its label from the registry (or its id
// when the registry has none, marked when it is spare) above its roles. A
// channel flagged not installed shows its label and the reason only, as a
// device that is not installed is not drawn.
// A channel with a widget class of its own (the pumps of the TIC station) is shown by that
// widget, the others by the rows of their device's widget.
const ChannelRoles = ({ id, channel, rows }) => {
  const cls = channelClass(id, channel);
  if (!cls) return <RoleGrid id={id} channel={channel} rows={rows} />;
  const Widget = widgetOf(cls);
  return <Widget id={id} channel={channel} />;
};

const Channels = ({ id, rows }) => (
  <Stack spacing={1.5}>
    {channelsOf(id).map((channel) => (
      <Stack key={channel} spacing={1} data-channel={channel}>
        <Typography variant="subtitle2">
          {channelLabel(id, channel) ?? channel}
          {isSpare(id, channel) && " · spare, not connected"}
          {!isChannelInstalled(id, channel) && ` · not installed: ${channelFlags(id, channel).not_installed}`}
        </Typography>
        {isChannelInstalled(id, channel) && <ChannelRoles id={id} channel={channel} rows={rows} />}
      </Stack>
    ))}
  </Stack>
);

export default Channels;
