import React, { useCallback, useEffect, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useEpicsPV } from "React-Automation-Studio/components/SystemComponents/EpicsPV";
import { alarmColors, alarmState, marker } from "../alarm/severity";
import { channelLabel, channelsOf, devices, installedDevices, iocs, rolesOf } from "../registry";
import PvLamp from "./fields/PvLamp";
import RoleField from "./RoleField";

const beatTimeout = 5000;

// Mode and heartbeat of one IOC; MAJOR when no beat came for 5 s
// (LAYOUT.md 1.4, IOC status). Reports the mode to the strip.
const IocChip = ({ ioc, onMode }) => {
  const theme = useTheme();
  const { name, roles } = iocs[ioc];
  const beat = useEpicsPV({ pv: roles.heartbeat });
  const mode = useEpicsPV({ pv: roles.mode, useStringValue: true });
  const [lastBeat, setLastBeat] = useState(Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => setLastBeat(Date.now()), [beat.value]);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const modeText = mode.initialized ? mode.value : null;
  useEffect(() => onMode(ioc, modeText), [ioc, modeText, onMode]);
  const silent = now - lastBeat > beatTimeout;
  const state = beat.initialized && silent ? "major" : alarmState(beat.initialized, beat.severity);
  const colors = alarmColors(theme, state);
  const beatText = !beat.initialized ? "no connection" : silent ? "heartbeat lost" : `♥ ${Number(beat.value)}`;
  return (
    <Chip
      size="small"
      variant="outlined"
      data-ioc={ioc}
      data-alarm={state}
      label={`${name}: ${modeText ?? "mode ?"} · ${beatText} ${marker(state)}`}
      sx={{
        background: colors.fill,
        borderColor: state === "ok" ? undefined : colors.stroke,
        borderStyle: colors.dashed ? "dashed" : "solid",
      }}
    />
  );
};

// The banner text (LAYOUT.md 1.3), or null when every IOC reports "real".
const bannerText = (modes) => {
  const entries = Object.keys(iocs).map((ioc) => [iocs[ioc].name, modes[ioc]]);
  if (entries.every(([, mode]) => mode === "real")) return null;
  if (entries.every(([, mode]) => mode === "sim")) {
    return `EMULATOR — ${entries.map(([name]) => name).join(" and ")} report mode sim. No hardware is connected.`;
  }
  const parts = entries.map(([name, mode]) =>
    mode === "sim" ? `${name} in mode sim` : mode === "real" ? `${name} on real hardware` : `${name}: mode unknown`
  );
  return `${entries.some(([, mode]) => mode === "real") ? "MIXED" : "EMULATOR"} — ${parts.join(", ")}.`;
};

// The interlock summary: every interlock device with its inputs.
const InterlockSummary = () =>
  installedDevices()
    .filter((id) => devices[id].class === "interlock")
    .map((id) => (
      <Stack key={id} direction="row" spacing={2} alignItems="center">
        <RoleField id={id} role="open" />
        {channelsOf(id).map((channel) => (
          <PvLamp key={channel} pv={rolesOf(id, channel).state} label={channelLabel(id, channel) ?? channel} />
        ))}
      </Stack>
    ));

// Below the app bar of every window: the emulator banner, the IOC chips and
// the interlock summary. Sets the window title, with [SIM] while the banner
// shows. `compact` (device windows) leaves out the interlock summary.
const StatusStrip = ({ title, compact = false }) => {
  const theme = useTheme();
  const [modes, setModes] = useState({});
  const onMode = useCallback((ioc, mode) => setModes((m) => ({ ...m, [ioc]: mode })), []);
  const banner = bannerText(modes);
  useEffect(() => {
    document.title = `${banner ? "[SIM] " : ""}${title}`;
  }, [banner, title]);
  const { main, dark } = theme.palette.emulator;
  return (
    <Stack
      direction={compact ? "column" : "row"}
      spacing={1}
      alignItems={compact ? "stretch" : "center"}
      sx={{ px: 1, py: 0.5, background: theme.palette.background.paper }}
    >
      <Box
        data-banner={banner ? "shown" : "hidden"}
        sx={{
          flexGrow: 1,
          px: 1.5,
          py: 0.5,
          minHeight: 28,
          background: banner ? `repeating-linear-gradient(135deg, ${main} 0 14px, ${dark} 14px 28px)` : "none",
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 700, color: "#fff" }}>
          {banner}
        </Typography>
      </Box>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        {Object.keys(iocs).map((ioc) => (
          <IocChip key={ioc} ioc={ioc} onMode={onMode} />
        ))}
      </Stack>
      {!compact && <InterlockSummary />}
    </Stack>
  );
};

export default StatusStrip;
