import React from "react";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmColors, alarmState, displayText } from "../../alarm/severity";
import { valueText } from "./format";

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

const PvLampComponent = (props) => {
  const state = alarmState(props.initialized, props.alarmSeverity);
  return (
    <Stack direction="row" spacing={1} alignItems="center" data-pv={props.pv} data-alarm={state}>
      <Lamp state={state} on={Number(props.value) !== 0} />
      <Typography variant="body2" color="text.secondary" noWrap>
        {props.label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 500 }} noWrap data-value>
        {displayText(state, valueText(props))}
      </Typography>
    </Stack>
  );
};

// A binary read-back as a lamp with its word; `custom_selection_strings` are
// the registry's words.
const PvLamp = (props) => <Widget {...props} component={PvLampComponent} />;

export default PvLamp;
