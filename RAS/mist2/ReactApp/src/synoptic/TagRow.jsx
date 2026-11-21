import React from "react";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmColors, alarmState, displayText } from "../alarm/severity";
import { Lamp, lampText } from "../components/fields/PvLamp";
import valueFormat from "../components/fields/valueFormat";
import { exponentRoles, isLamp, lampWords } from "../roles";

export const rowHeight = 18;

const TagRowComponent = (props) => {
  const theme = useTheme();
  const { x, y, w, lamp } = props;
  const state = alarmState(props.initialized, props.alarmSeverity);
  const colors = alarmColors(theme, state);
  const text = lamp
    ? lampText(state, props.value, props.enumStrs)
    : displayText(state, props.value, props.units);
  return (
    <g data-pv={props.pv} data-alarm={state}>
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
        {props.label}
      </text>
      {lamp && <Lamp x={x + w - 100} y={y + 2} size={13} state={state} on={Number(props.value) !== 0} />}
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
    </g>
  );
};

// One value of a tag, in the shared alarm look, with the RAS context menu.
const TagRow = ({ pv, role, ...others }) => {
  const lamp = isLamp(pv, role);
  const format = lamp
    ? { custom_selection_strings: lampWords[role] }
    : valueFormat(pv, exponentRoles.includes(role));
  return <Widget {...others} {...format} svgWidget pv={pv} lamp={lamp} component={TagRowComponent} />;
};

export default TagRow;
