import React, { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import Box from "@mui/material/Box";
import CssBaseline from "@mui/material/CssBaseline";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import { AlarmChip } from "../alarm/AlarmMarks";
import { AlarmProvider, useWorstAlarm } from "../alarm/AlarmStore";
import { widgetOf } from "../components/devices";
import ExpertView from "../components/ExpertView";
import Flags from "../components/Flags";
import StatusStrip from "../components/StatusStrip";
import TrendSet from "../components/TrendSet";
import { alarmPvs, channelLabel, devices, iocOf, isPolled } from "../registry";
import { trendPvs } from "../roles";

const parts = ["Controls", "Trend", "Expert"];

const DeviceHeader = ({ id, channel }) => {
  const device = devices[id];
  const state = useWorstAlarm(alarmPvs(id));
  return (
    <Stack spacing={0.5} sx={{ px: 1.5, pt: 1 }}>
      <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
        <Typography variant="h6" noWrap>
          {device.name}
        </Typography>
        {isPolled(id) && <AlarmChip state={state} />}
      </Stack>
      <Typography variant="caption" color="text.secondary">
        {device.model} · {iocOf(id).name} · {device.page}
        {channel && ` · opened from ${channelLabel(id, channel) ?? channel}`}
      </Typography>
    </Stack>
  );
};

// A device in a browser window of its own (owner's decision at G2): name,
// emulator banner and own severity, then Controls, Trend and Expert. All
// three stay mounted so that the trend keeps its history. An ordinary route,
// /device/<registry id>, so it can be opened by its address as well.
const DeviceWindow = () => {
  const { id } = useParams();
  const [params] = useSearchParams();
  const [part, setPart] = useState(Math.max(0, parts.indexOf(params.get("part"))));
  // Plotly sizes a graph on window resize; one that was hidden needs a nudge.
  useEffect(() => {
    window.dispatchEvent(new Event("resize"));
  }, [part]);
  if (!devices[id]) return <Typography sx={{ p: 2 }}>No device {id} in the registry.</Typography>;
  const DeviceWidget = widgetOf(devices[id].class);
  return (
    <AlarmProvider pvs={alarmPvs(id)}>
      <CssBaseline />
      <StatusStrip title={devices[id].name} compact />
      <DeviceHeader id={id} channel={params.get("channel")} />
      <Box sx={{ px: 1.5, pt: 1 }}>
        <Flags id={id} />
      </Box>
      <Tabs value={part} onChange={(event, value) => setPart(value)} variant="fullWidth">
        {parts.map((name) => (
          <Tab key={name} label={name} />
        ))}
      </Tabs>
      <Box sx={{ p: 1.5 }} data-part="Controls" hidden={part !== 0}>
        <Box sx={{ opacity: isPolled(id) ? 1 : 0.5 }}>
          <DeviceWidget id={id} />
        </Box>
      </Box>
      <Box sx={{ p: 1 }} data-part="Trend" hidden={part !== 1}>
        <TrendSet pvs={trendPvs(id)} size={12} height={220} />
      </Box>
      <Box sx={{ p: 1 }} data-part="Expert" hidden={part !== 2}>
        <ExpertView id={id} />
      </Box>
    </AlarmProvider>
  );
};

export default DeviceWindow;
