import React from "react";
import { useTheme } from "@mui/material/styles";
import { useEpicsPV } from "React-Automation-Studio/components/SystemComponents/EpicsPV";
import { useWorstAlarm } from "../alarm/AlarmStore";
import { alarmColors } from "../alarm/severity";
import { alarmPvs, rolesOf } from "../registry";
import { openDeviceWindow } from "../windows";

// The shapes of the synoptic symbols, centred on (0, 0). `on` fills them.
const shapes = {
  electrode: () => (
    <>
      <rect x={-5} y={-75} width={10} height={50} />
      <rect x={-5} y={25} width={10} height={50} />
    </>
  ),
  valve: () => <path d="M -13 -9 L 0 0 L -13 9 Z M 13 -9 L 0 0 L 13 9 Z" />,
  gauge: (theme) => (
    <>
      <circle r={12} />
      <text y={4} fontSize={12} textAnchor="middle" fill={theme.palette.text.primary} stroke="none">
        G
      </text>
    </>
  ),
  turbo: () => (
    <>
      <circle r={24} />
      <path d="M -17 -17 L 17 17 M -17 17 L 17 -17" fill="none" />
    </>
  ),
  // a backing pump (the TIC cart's, T32): a circle with the triangle of a pump
  pump: () => (
    <>
      <circle r={16} />
      <path d="M -9 9 L 0 -12 L 9 9" fill="none" />
    </>
  ),
  cup: () => <path d="M -16 -14 L -16 14 L 16 14 L 16 -14 L 10 -14 L 10 8 L -10 8 L -10 -14 Z" />,
  filament: () => <path d="M -22 22 L -22 -4 L 0 -26 L 22 -4 L 22 22" fill="none" strokeWidth={4} />,
};

const SymbolShape = ({ type, x, y, rotate = 0, state, on }) => {
  const theme = useTheme();
  const colors = alarmColors(theme, state);
  const color = state === "ok" ? theme.palette.text.secondary : colors.stroke;
  const live = on && state !== "invalid" && state !== "disconnected";
  return (
    <g
      transform={`translate(${x} ${y}) rotate(${rotate})`}
      stroke={color}
      strokeWidth={2}
      strokeDasharray={colors.dashed ? "4 3" : undefined}
      fill={live ? (state === "ok" ? theme.palette.primary.main : color) : theme.palette.background.paper}
    >
      {shapes[type](theme)}
    </g>
  );
};

const StateShape = ({ pv, ...shape }) => {
  const { value } = useEpicsPV({ pv });
  return <SymbolShape {...shape} on={Number(value) !== 0} />;
};

// A symbol of the drawing: coloured by the worst alarm state of its device or
// channel, filled while the record of its state role is not 0. A click opens
// the device window.
const Symbol = ({ id, channel, type, x, y, rotate, state: stateRole }) => {
  const state = useWorstAlarm(alarmPvs(id, channel));
  const statePv = stateRole && rolesOf(id, channel)[stateRole];
  const shape = { type, x, y, rotate, state };
  return (
    <g onClick={() => openDeviceWindow(id, channel)} style={{ cursor: "pointer" }} data-symbol={type}>
      {statePv ? (
        <StateShape pv={statePv} {...shape} />
      ) : (
        <SymbolShape {...shape} />
      )}
    </g>
  );
};

export default Symbol;
