import React from "react";
import Button from "@mui/material/Button";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmColors, alarmState } from "../../alarm/severity";

const PvActionComponent = (props) => {
  const theme = useTheme();
  const state = alarmState(props.initialized, props.alarmSeverity);
  const colors = alarmColors(theme, state);
  return (
    <Button
      variant="outlined"
      color="inherit"
      size={props.size}
      disabled={props.disabled}
      onClick={() => props.handleImmediateChange(1)}
      data-pv={props.pv}
      data-alarm={state}
      sx={{
        fontWeight: 700,
        whiteSpace: "nowrap",
        borderWidth: 2,
        borderColor: state === "ok" ? undefined : colors.stroke,
        borderStyle: colors.dashed ? "dashed" : "solid",
      }}
    >
      {props.label}
    </Button>
  );
};

// A one-shot command (ALL HV OFF): a click writes 1, the record resets itself.
const PvAction = (props) => <Widget {...props} component={PvActionComponent} />;

export default PvAction;
