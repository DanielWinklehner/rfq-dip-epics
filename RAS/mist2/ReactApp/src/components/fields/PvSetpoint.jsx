import React, { useState } from "react";
import InputAdornment from "@mui/material/InputAdornment";
import TextField from "@mui/material/TextField";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmState, alarmWord, fieldSx, marker } from "../../alarm/severity";

const PvSetpointComponent = (props) => {
  const theme = useTheme();
  const [editing, setEditing] = useState(false);
  const state = alarmState(props.initialized, props.alarmSeverity);
  // While the operator types, the field holds the typed text; otherwise it
  // shows the record like any other field, the word included.
  const shown = (!editing && alarmWord(state)) || props.value;
  return (
    <TextField
      size="small"
      label={props.label}
      value={shown}
      disabled={props.disabled}
      onFocus={() => {
        setEditing(true);
        props.handleFocus();
      }}
      onBlur={() => {
        setEditing(false);
        props.handleBlur();
      }}
      onChange={(event) => props.handleChange(event.target.value)}
      onKeyDown={(event) => event.key === "Enter" && props.handleCommitChange()}
      sx={fieldSx(theme, state)}
      slotProps={{
        input: {
          endAdornment: (
            <InputAdornment position="end">
              {[props.units, marker(state)].filter(Boolean).join(" ")}
            </InputAdornment>
          ),
        },
        htmlInput: { "data-pv": props.pv, "data-alarm": state },
      }}
    />
  );
};

// A set point: typed, sent with Enter. Unit and precision from the record.
const PvSetpoint = (props) => (
  <Widget {...props} component={PvSetpointComponent} usePvUnits usePvPrecision />
);

export default PvSetpoint;
