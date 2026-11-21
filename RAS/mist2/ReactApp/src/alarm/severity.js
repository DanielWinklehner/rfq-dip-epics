import { alpha } from "@mui/material/styles";

// The one place that decides how an alarm state looks (LAYOUT.md 1.2). Every
// field, lamp, tag, symbol, tab and chip of the GUI takes its colours, marker
// and word from here. The state comes from the record's severity alone.

const severityStates = ["ok", "minor", "major", "invalid"];
const rank = { ok: 0, minor: 1, major: 2, invalid: 3, disconnected: 4 };

// "disconnected" while Channel Access has no connection, else the severity.
export const alarmState = (initialized, severity) =>
  initialized ? (severityStates[Number(severity)] ?? "invalid") : "disconnected";

export const worst = (states) =>
  states.reduce((a, b) => (rank[b] > rank[a] ? b : a), "ok");

// Marker after the value and the word that replaces it. The marker carries the
// state for grayscale printouts and colour-blind readers.
const markers = { ok: "", minor: "▲", major: "■", invalid: "?", disconnected: "×" };
const words = { invalid: "INVALID", disconnected: "no connection" };
export const stateNames = {
  ok: "NO_ALARM",
  minor: "MINOR",
  major: "MAJOR",
  invalid: "INVALID",
  disconnected: "no connection",
};

export const marker = (state) => markers[state];
export const alarmWord = (state) => words[state];

// The text a value field shows: the value with its unit and marker, or the
// word that replaces it when the value cannot be trusted.
export const displayText = (state, value, units) =>
  words[state] ??
  [value, units, markers[state]].filter((part) => part !== "" && part != null).join(" ");

// Colours of a state: fill, stroke (border or outline), text, dashed outline.
export const alarmColors = (theme, state) => {
  if (state === "ok") {
    return {
      fill: "transparent",
      stroke: theme.palette.divider,
      text: theme.palette.text.primary,
      dashed: false,
    };
  }
  const main = theme.palette.alarm[state].main;
  return {
    fill: alpha(main, 0.3),
    stroke: main,
    text: theme.palette.mode === "dark" ? theme.palette.common.white : theme.palette.common.black,
    dashed: state === "disconnected",
  };
};

// sx for a MUI outlined TextField in a state.
export const fieldSx = (theme, state) => {
  const colors = alarmColors(theme, state);
  return {
    width: "100%",
    "& .MuiOutlinedInput-root": { background: colors.fill },
    "& .MuiOutlinedInput-notchedOutline": {
      borderColor: state === "ok" ? undefined : colors.stroke,
      borderStyle: colors.dashed ? "dashed" : "solid",
      borderWidth: state === "ok" ? undefined : 2,
    },
    "& .MuiInputBase-input": {
      fontWeight: state === "ok" ? undefined : 600,
      fontStyle: state === "disconnected" ? "italic" : undefined,
    },
  };
};
