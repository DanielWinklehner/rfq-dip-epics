import React from "react";
import { useTheme } from "@mui/material/styles";
import { alarmColors } from "../alarm/severity";
import { Lamp } from "../components/fields/PvLamp";
import useReading from "../components/fields/useReading";

export const rowHeight = 18;

// One value of a tag, in the shared alarm look, with the RAS context menu.
// A value with two words (registry) gets a lamp.
const TagRow = ({ pv, words, label, x, y, w }) => {
  const theme = useTheme();
  const { state, text, on, menu, openMenu } = useReading(pv, words);
  const colors = alarmColors(theme, state);
  return (
    <g data-pv={pv} data-alarm={state} onContextMenu={openMenu}>
      <rect
        x={x + 2}
        y={y}
        width={w - 4}
        height={rowHeight - 1}
        fill={colors.fill}
        stroke={state === "ok" ? "none" : colors.stroke}
        strokeDasharray={colors.dashed ? "3 2" : undefined}
      />
      <text x={x + 7} y={y + 13} fontSize={11} fill={theme.palette.text.secondary}>
        {label}
      </text>
      {words?.length === 2 && <Lamp x={x + w - 100} y={y + 2} size={13} state={state} on={on} />}
      <text
        x={x + w - 7}
        y={y + 13}
        fontSize={12}
        fontWeight={600}
        textAnchor="end"
        fill={state === "ok" ? theme.palette.text.primary : colors.text}
        data-value
      >
        {text}
      </text>
      {menu}
    </g>
  );
};

export default TagRow;
