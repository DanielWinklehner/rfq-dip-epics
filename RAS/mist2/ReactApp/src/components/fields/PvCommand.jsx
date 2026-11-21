import React, { useState } from "react";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import FormHelperText from "@mui/material/FormHelperText";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { alarmColors, alarmState, alarmWord, marker } from "../../alarm/severity";
import stateText from "./stateText";

const PvCommandComponent = (props) => {
  const theme = useTheme();
  const [asked, setAsked] = useState(null);
  const state = alarmState(props.initialized, props.alarmSeverity);
  const colors = alarmColors(theme, state);
  const send = (value) => {
    if (props.confirm?.value === value) setAsked(value);
    else props.handleImmediateChange(value);
  };
  return (
    <Stack spacing={0.5} data-pv={props.pv} data-alarm={state}>
      <Typography variant="caption" color="text.secondary">
        {props.label}
        {state !== "ok" && ` · ${alarmWord(state) ?? state.toUpperCase()} ${marker(state)}`}
      </Typography>
      <ToggleButtonGroup
        exclusive
        size="small"
        fullWidth
        disabled={props.disabled}
        value={Number(props.value)}
        onChange={(event, value) => value !== null && send(value)}
        sx={{
          outline: state === "ok" ? undefined : `2px ${colors.dashed ? "dashed" : "solid"} ${colors.stroke}`,
        }}
      >
        {[0, 1].map((value) => (
          <ToggleButton key={value} value={value}>
            {stateText(value, props.enumStrs)}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      {props.helperText && <FormHelperText>{props.helperText}</FormHelperText>}
      <Dialog open={asked !== null} onClose={() => setAsked(null)}>
        <DialogTitle>Confirm</DialogTitle>
        <DialogContent>{props.confirm?.text}</DialogContent>
        <DialogActions>
          <Button onClick={() => setAsked(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              props.handleImmediateChange(asked);
              setAsked(null);
            }}
          >
            {stateText(asked, props.enumStrs)}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
};

// A binary request (output, valve, pump, gauge): one button per state, the
// state strings from the record. `confirm` = { value, text } asks first.
const PvCommand = (props) => <Widget {...props} component={PvCommandComponent} />;

export default PvCommand;
