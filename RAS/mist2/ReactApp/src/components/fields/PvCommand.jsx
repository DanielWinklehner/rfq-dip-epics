import React, { useState } from "react";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import Widget from "React-Automation-Studio/components/SystemComponents/Widgets/Widget";
import { useEpicsPV } from "React-Automation-Studio/components/SystemComponents/EpicsPV";
import { alarmColors, alarmState, alarmWord, marker } from "../../alarm/severity";

// The registry's question for a value: `confirm` is one { value, text } or a
// list of them (a pump's start and stop, T32).
const questionFor = (confirm, value) => [].concat(confirm ?? []).find((ask) => ask.value === value);

// A warning in the question ({ pv, unless, text }): shown unless the PV is
// connected, valid and reads `unless` (the foreline valve closed before the
// cart's turbopump is stopped). Read while the question is open; until the PV
// has connected its state is not known, so the warning shows.
const Warning = ({ warn }) => {
  const pv = useEpicsPV({ pv: warn.pv });
  const known = pv.initialized && Number(pv.severity) < 3 && Number(pv.value) === Number(warn.unless);
  if (known) return null;
  return (
    <Typography color="error" fontWeight={600} sx={{ mt: 1.5 }} data-warning={warn.pv}>
      {warn.text}
    </Typography>
  );
};

const PvCommandComponent = (props) => {
  const theme = useTheme();
  const [asked, setAsked] = useState(null);
  const state = alarmState(props.initialized, props.alarmSeverity);
  const colors = alarmColors(theme, state);
  const question = asked === null ? null : questionFor(props.confirm, asked);
  const send = (value) => {
    if (questionFor(props.confirm, value)) setAsked(value);
    else props.handleImmediateChange(value);
  };
  return (
    <Stack spacing={0.5} data-pv={props.pv} data-alarm={state}>
      {!props.dense && (
        <Typography variant="caption" color="text.secondary">
          {props.label}
          {state !== "ok" && ` · ${alarmWord(state) ?? state.toUpperCase()} ${marker(state)}`}
        </Typography>
      )}
      <ToggleButtonGroup
        exclusive
        size="small"
        fullWidth
        disabled={props.disabled}
        value={Number(props.value)}
        onChange={(event, value) => value !== null && send(value)}
        aria-label={props.label}
        sx={{
          outline: state === "ok" ? undefined : `2px ${colors.dashed ? "dashed" : "solid"} ${colors.stroke}`,
          background: colors.fill,
          ...(props.dense && { height: 22, "& .MuiToggleButton-root": { py: 0, px: 0.5, fontSize: 11, lineHeight: 1.2 } }),
        }}
      >
        {[0, 1].map((value) => (
          <ToggleButton key={value} value={value}>
            {props.enumStrs?.[value] ?? value}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      <Dialog open={asked !== null} onClose={() => setAsked(null)}>
        <DialogTitle>Confirm</DialogTitle>
        <DialogContent>
          {question?.text}
          {question?.warn && <Warning warn={question.warn} />}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAsked(null)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => {
              props.handleImmediateChange(asked);
              setAsked(null);
            }}
          >
            {props.enumStrs?.[asked] ?? asked}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
};

// A binary request (output, valve, pump, gauge, loop mode): one button per
// state, named by the registry's words (custom_selection_strings). `confirm` =
// { value, text } from the registry, or a list of them, asks first, with a
// warning where the question has one. `dense`: the form inside a
// tag, without the label (the tag row has it).
const PvCommand = (props) => <Widget {...props} component={PvCommandComponent} />;

export default PvCommand;
