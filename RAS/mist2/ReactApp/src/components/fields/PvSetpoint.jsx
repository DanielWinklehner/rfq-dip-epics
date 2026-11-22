import React, { useState } from "react";
import InputAdornment from "@mui/material/InputAdornment";
import TextField from "@mui/material/TextField";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmState, alarmWord, fieldSx, marker } from "../../alarm/severity";

// The mark of a typed entry that has not been sent: a dashed outline in the
// theme's info colour (no alarm uses it) and ↵ after the unit, "press Enter".
const unsentSx = (theme) => ({
  "& .MuiOutlinedInput-notchedOutline": {
    borderColor: `${theme.palette.info.main} !important`,
    borderStyle: "dashed",
    borderWidth: 2,
  },
  "& .MuiInputBase-input": { fontStyle: "italic" },
});

// The tag form: no label of its own (the tag row has it), one line high.
const denseSx = {
  "& .MuiInputBase-root": { fontSize: 12, height: 22, pr: 0.75 },
  "& .MuiInputBase-input": { py: 0, px: 0.75, textAlign: "right" },
  "& .MuiInputAdornment-root": { ml: 0.5, "& p": { fontSize: 11 } },
};

const PvSetpointComponent = (props) => {
  const theme = useTheme();
  const [editing, setEditing] = useState(false);
  const [unsent, setUnsent] = useState(false);
  const state = alarmState(props.initialized, props.alarmSeverity);
  // While the operator types, the field holds the typed text; otherwise it
  // shows the record like any other field, the word included. Leaving the
  // field, or Escape, gives the entry up: RAS Widget shows the record's value
  // again as soon as the field is not focused.
  const shown = (!editing && alarmWord(state)) || props.value;
  const units = [props.units, marker(state), unsent && "↵"].filter(Boolean).join(" ");
  return (
    <TextField
      size="small"
      label={props.dense ? undefined : props.label}
      value={shown}
      disabled={props.disabled}
      onFocus={() => {
        setEditing(true);
        props.handleFocus();
      }}
      onBlur={() => {
        setEditing(false);
        setUnsent(false);
        props.handleBlur();
      }}
      onChange={(event) => {
        setUnsent(true);
        props.handleChange(event.target.value);
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          setUnsent(false);
          props.handleCommitChange();
        }
        if (event.key === "Escape") event.target.blur();
      }}
      sx={[fieldSx(theme, state), props.dense && denseSx, unsent && unsentSx(theme)]}
      slotProps={{
        input: {
          endAdornment: <InputAdornment position="end">{units}</InputAdornment>,
        },
        htmlInput: {
          "data-pv": props.pv,
          "data-alarm": state,
          "data-unsent": unsent ? "true" : undefined,
          "aria-label": props.label,
        },
      }}
    />
  );
};

// A set point: typed, sent with Enter, given up with Escape or by leaving the
// field. A text field, so the mouse wheel and the arrow keys change nothing.
// Unit and precision from the record. `dense`: the form inside a tag.
const PvSetpoint = (props) => (
  <Widget {...props} component={PvSetpointComponent} usePvUnits usePvPrecision />
);

export default PvSetpoint;
