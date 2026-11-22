import React from "react";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { alarmColors } from "../../alarm/severity";
import useReading from "./useReading";

// The lamp of a binary state (LAYOUT.md 1.2): filled when on, hollow when
// off, in the colour of the record's severity; crossed out without connection.
export const Lamp = ({ state, on, size = 14, x, y }) => {
  const theme = useTheme();
  const colors = alarmColors(theme, state);
  const color = state === "ok" ? theme.palette.text.primary : colors.stroke;
  const r = size / 2 - 1.5;
  return (
    <svg x={x} y={y} width={size} height={size} style={{ flex: "none" }}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill={on && state !== "invalid" && state !== "disconnected" ? color : "none"}
        stroke={color}
        strokeWidth={state === "invalid" ? 3 : 1.5}
        strokeDasharray={colors.dashed ? "2 2" : undefined}
      />
      {state === "disconnected" && (
        <line x1={2} y1={size - 2} x2={size - 2} y2={2} stroke={color} strokeWidth={1.5} />
      )}
    </svg>
  );
};

// A binary read-back as a lamp with its word; `words` are the registry's.
const PvLamp = ({ pv, label, words }) => {
  const { state, text, on, menu, openMenu } = useReading(pv, words);
  return (
    <Stack direction="row" spacing={1} alignItems="center" data-pv={pv} data-alarm={state} onContextMenu={openMenu}>
      <Lamp state={state} on={on} />
      <Typography variant="body2" color="text.secondary" noWrap>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 500 }} noWrap data-value>
        {text}
      </Typography>
      {menu}
    </Stack>
  );
};

export default PvLamp;
