import React from "react";
import TextField from "@mui/material/TextField";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmState, displayText, fieldSx } from "../../alarm/severity";
import { isText } from "../../registry";

const PvValueComponent = (props) => {
  const theme = useTheme();
  const state = alarmState(props.initialized, props.alarmSeverity);
  return (
    <TextField
      size="small"
      label={props.label}
      value={displayText(state, props.value, props.units)}
      helperText={props.helperText}
      sx={fieldSx(theme, state)}
      slotProps={{
        input: { readOnly: true },
        htmlInput: { "data-pv": props.pv, "data-alarm": state },
      }}
    />
  );
};

// A read-back: value, unit and precision from the record, coloured by its
// severity. `exponent` shows the number in exponent format (pressures).
const PvValue = ({ pv, exponent = false, ...others }) => {
  const text = isText(pv);
  return (
    <Widget
      {...others}
      pv={pv}
      component={PvValueComponent}
      useStringValue={text}
      usePvUnits
      usePvPrecision={!text && !exponent}
      numberFormat={exponent ? { notation: "exponential", precision: 3 } : undefined}
    />
  );
};

export default PvValue;
