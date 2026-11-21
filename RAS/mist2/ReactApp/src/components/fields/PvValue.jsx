import React from "react";
import TextField from "@mui/material/TextField";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmState, displayText, fieldSx } from "../../alarm/severity";
import { readProps, valueText } from "./format";

const PvValueComponent = (props) => {
  const theme = useTheme();
  const state = alarmState(props.initialized, props.alarmSeverity);
  return (
    <TextField
      size="small"
      label={props.label}
      value={displayText(state, valueText(props))}
      sx={fieldSx(theme, state)}
      slotProps={{
        input: { readOnly: true },
        htmlInput: { "data-pv": props.pv, "data-alarm": state },
      }}
    />
  );
};

// A read-back: its word, or value and unit from the record, coloured by its
// severity. `words` are the registry's words for the values.
const PvValue = ({ pv, words, ...others }) => (
  <Widget {...others} pv={pv} component={PvValueComponent} {...readProps(pv, words)} />
);

export default PvValue;
