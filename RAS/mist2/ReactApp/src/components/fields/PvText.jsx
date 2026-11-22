import React from "react";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmColors, alarmState, displayText } from "../../alarm/severity";
import { readProps, valueText } from "./format";

const PvTextComponent = (props) => {
  const theme = useTheme();
  const state = alarmState(props.initialized, props.alarmSeverity);
  const colors = alarmColors(theme, state);
  return (
    <Typography
      variant="body2"
      component="span"
      data-pv={props.pv}
      data-alarm={state}
      sx={{
        px: 0.5,
        background: colors.fill,
        outline: state === "ok" ? undefined : `1px ${colors.dashed ? "dashed" : "solid"} ${colors.stroke}`,
        overflowWrap: "anywhere",
      }}
    >
      {displayText(state, valueText(props))}
    </Typography>
  );
};

// A value inline in text or a table cell. `field` reads another field of the
// record (VAL$ for the full text of a long string).
const PvText = ({ pv, field, ...others }) => (
  <Widget
    {...others}
    pv={field ? `${pv}.${field}` : pv}
    component={PvTextComponent}
    componentProps={{ pv }}
    {...readProps(pv)}
  />
);

export default PvText;
