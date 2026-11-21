import React from "react";
import Chip from "@mui/material/Chip";
import { useTheme } from "@mui/material/styles";
import { alarmColors, marker, stateNames } from "./severity";

// The worst state of a tab or page as a dot (LAYOUT.md 1.2).
export const AlarmDot = ({ state }) => {
  const theme = useTheme();
  const colors = alarmColors(theme, state);
  return (
    <svg width={12} height={12} data-alarm={state} style={{ marginLeft: 6 }}>
      <circle
        cx={6}
        cy={6}
        r={4.5}
        fill={state === "ok" ? "none" : colors.stroke}
        stroke={state === "ok" ? theme.palette.text.disabled : colors.stroke}
        strokeDasharray={colors.dashed ? "2 2" : undefined}
      />
    </svg>
  );
};

// A state as a chip with its name and marker; `label` goes in front.
export const AlarmChip = ({ state, label }) => {
  const theme = useTheme();
  const colors = alarmColors(theme, state);
  return (
    <Chip
      size="small"
      variant="outlined"
      data-alarm={state}
      label={[label, stateNames[state], marker(state)].filter(Boolean).join(" ")}
      sx={{
        background: colors.fill,
        borderColor: state === "ok" ? undefined : colors.stroke,
        borderStyle: colors.dashed ? "dashed" : "solid",
        borderWidth: state === "ok" ? 1 : 2,
        fontWeight: state === "ok" ? undefined : 700,
      }}
    />
  );
};
