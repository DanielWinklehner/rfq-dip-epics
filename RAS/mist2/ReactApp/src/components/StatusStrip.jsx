import React, { useCallback, useEffect, useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useEpicsPV } from "React-Automation-Studio/components/SystemComponents/EpicsPV";
import { alarmColors, alarmState, marker } from "../alarm/severity";
import { channelLabel, connectedChannels, devices, infrastructureDevices, installedDevices, iocs, rolesOf, wordsOf } from "../registry";
import { roleText } from "../roles";
import { openDeviceWindow } from "../windows";
import PvLamp from "./fields/PvLamp";
import useReading from "./fields/useReading";
import RoleField from "./RoleField";
import modeSummary from "./modeSummary";

const beatTimeout = 5000;

// Mode and heartbeat of one IOC; MAJOR when no beat came for 5 s
// (LAYOUT.md 1.4, IOC status). Reports the mode to the strip.
const IocChip = ({ ioc, onMode }) => {
  const theme = useTheme();
  const { name, roles } = iocs[ioc];
  const beat = useEpicsPV({ pv: roles.heartbeat });
  const mode = useEpicsPV({ pv: roles.mode, useStringValue: true });
  // When the beat last changed. Taken at render, not set from an effect.
  const lastBeat = useMemo(() => Date.now(), [beat.value]);
  const [now, setNow] = useState(Date.now());
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

// A service of the control system (the data logger) by its role `alive`, in
// the shared alarm look: dead (0, MAJOR) shows on every window. A click opens
// its device window.
const AliveChip = ({ id }) => {
  const theme = useTheme();
  const pv = rolesOf(id).alive;
  const words = wordsOf(id, undefined, "alive");
  const { state, text, menu, openMenu } = useReading(pv, words);
  const colors = alarmColors(theme, state);
  const name = words ? devices[id].name : `${devices[id].name} ${roleText(id, "alive")}`;
  return (
    <>
      <Chip
        size="small"
        variant="outlined"
        data-service={id}
        data-pv={pv}
        data-alarm={state}
        label={`${name}: ${text}`}
        onClick={() => openDeviceWindow(id)}
        onContextMenu={openMenu}
        sx={{
          background: colors.fill,
          borderColor: state === "ok" ? undefined : colors.stroke,
          borderStyle: colors.dashed ? "dashed" : "solid",
          borderWidth: state === "ok" ? 1 : 2,
          fontWeight: state === "ok" ? undefined : 700,
        }}
      />
      {menu}
    </>
  );
};

const services = infrastructureDevices.filter((id) => rolesOf(id).alive);

// The interlock summary: every interlock device with its inputs.
const InterlockSummary = () =>
  installedDevices()
    .filter((id) => devices[id].class === "interlock")
    .map((id) => (
      <Stack key={id} direction="row" spacing={2} alignItems="center">
        <RoleField id={id} role="open" />
        {connectedChannels(id).map((channel) => (
          <PvLamp
            key={channel}
            pv={rolesOf(id, channel).state}
            label={channelLabel(id, channel) ?? channel}
            words={wordsOf(id, channel, "state")}
          />
        ))}
      </Stack>
    ));

// Below the app bar of every window: the emulator banner, the IOC chips, the
// chips of the services (the data logger) and the interlock summary. Sets the window title, with
// [SIM] for the emulation and [MIXED] for a mix (modeSummary.js). `compact` (device windows) leaves out the interlock summary.
const StatusStrip = ({ title, compact = false }) => {
  const theme = useTheme();
  const [modes, setModes] = useState({});
  const onMode = useCallback((ioc, mode) => setModes((m) => ({ ...m, [ioc]: mode })), []);
  const { prefix, banner, kind } = modeSummary(Object.keys(iocs).map((ioc) => [iocs[ioc].name, modes[ioc]]));
  useEffect(() => {
    document.title = `${prefix}${title}`;
  }, [prefix, title]);
  // The emulator's stripes for the emulation and a mix; a neutral grey when a
  // mode is not known.
  const { main, dark } = kind === "unknown" ? { main: theme.palette.grey[600], dark: theme.palette.grey[800] } : theme.palette.emulator;
  return (
    <Stack
      direction={compact ? "column" : "row"}
      spacing={1}
      alignItems={compact ? "stretch" : "center"}
      sx={{ px: 1, py: 0.5, background: theme.palette.background.paper }}
    >
      <Box
        data-banner={banner ? "shown" : "hidden"}
        data-mode={kind}
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
        {services.map((id) => (
          <AliveChip key={id} id={id} />
        ))}
      </Stack>
      {!compact && <InterlockSummary />}
    </Stack>
  );
};

export default StatusStrip;
