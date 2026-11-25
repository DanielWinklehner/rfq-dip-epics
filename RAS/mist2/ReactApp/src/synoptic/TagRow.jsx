import React from "react";
import { useTheme } from "@mui/material/styles";
import { alarmColors } from "../alarm/severity";
import RoleField from "../components/RoleField";
import { Lamp } from "../components/fields/PvLamp";
import useReading from "../components/fields/useReading";

export const rowHeight = 18;
export const setRowHeight = 26;
export const heightOf = (row) => (row.set ? setRowHeight : rowHeight);

const Label = ({ x, y, children }) => {
  const theme = useTheme();
  return (
    <text x={x + 7} y={y + 13} fontSize={11} fill={theme.palette.text.secondary}>
      {children}
    </text>
  );
};

// One value of a tag, in the shared alarm look, with the RAS context menu.
// A value with two words (registry) gets a lamp.
const ReadRow = ({ pv, words, label, x, y, w, stateWord }) => {
  const theme = useTheme();
  const { state, text, on, menu, openMenu } = useReading(pv, words);
  const why = state !== "ok" && stateWord ? stateWord(state) : null;
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
      <Label x={x} y={y}>
        {label}
        {why && (
          <tspan data-state-word fontWeight={700} fill={theme.palette.text.primary}>
            {` · ${why}`}
          </tspan>
        )}
      </Label>
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

// What the operator sets, where it stands: the field of the device window in
// its tag form, as HTML in a foreignObject. It is laid out in the drawing's
// own coordinates, so it scales and stays aligned with the SVG at every window
// size, and the browser draws its text as text, sharp at any scale. A click in
// it does not reach the tag (which opens the device window).
const SetRow = ({ id, channel, role, label, x, y, w }) => {
  const field = Math.round(w * 0.56);
  return (
    <g data-set={role}>
      <Label x={x} y={y + 4}>
        {label}
      </Label>
      <foreignObject x={x + w - field - 4} y={y + 2} width={field} height={setRowHeight - 4}>
        <div onClick={(event) => event.stopPropagation()}>
          <RoleField id={id} channel={channel} role={role} label={label} dense />
        </div>
      </foreignObject>
    </g>
  );
};

// A read row with the device's state beside it (tagRows: statePv): the
// state's word, when the state itself is read without INVALID.
const StatedReadRow = ({ statePv, stateWords, ...row }) => {
  const reading = useReading(statePv, stateWords);
  const word = ["ok", "minor", "major"].includes(reading.state) ? reading.text.replace(/ [▲■?×]$/, "") : null;
  return <ReadRow {...row} stateWord={() => word} />;
};

const TagRow = (row) =>
  row.set ? <SetRow {...row} /> : row.statePv ? <StatedReadRow {...row} /> : <ReadRow {...row} />;

export default TagRow;
