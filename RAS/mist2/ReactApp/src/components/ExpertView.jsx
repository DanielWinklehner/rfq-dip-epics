import React from "react";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { useEpicsPV } from "React-Automation-Studio/components/SystemComponents/EpicsPV";
import { alarmColors, alarmState, stateNames, statusName } from "../alarm/severity";
import { devices, iocOf, isLongString, pvInfo, pvsOf, rolesOf, simulators } from "../registry";
import { roleText } from "../roles";
import PvText from "./fields/PvText";

const pad = (n, width = 2) => String(n).padStart(width, "0");
const epicsEpoch = 631152000;
const formatTime = (seconds) => {
  if (!seconds) return "";
  if (Number(seconds) <= epicsEpoch) return "never processed";
  const t = new Date(Number(seconds) * 1000);
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())} ${pad(t.getHours())}:${pad(
    t.getMinutes()
  )}:${pad(t.getSeconds())}.${pad(t.getMilliseconds(), 3)}`;
};

// One record: value (the last one, also when it is not to be trusted),
// severity, alarm status (the field STAT, which pvServer does not send) and
// time stamp.
const RecordRow = ({ name }) => {
  const theme = useTheme();
  const info = pvInfo(name);
  const array = ["aai", "waveform"].includes(info.type);
  const pv = useEpicsPV({ pv: isLongString(name) ? `${name}.VAL$` : name, useStringValue: !array });
  const stat = useEpicsPV({ pv: `${name}.STAT`, useStringValue: true });
  const state = alarmState(pv.initialized, pv.severity);
  const colors = alarmColors(theme, state);
  const cell = { px: 0.5, py: 0.25, fontSize: 12 };
  return (
    <TableRow data-pv={name} data-alarm={state} sx={{ background: colors.fill }}>
      <TableCell sx={{ ...cell, fontFamily: "monospace", wordBreak: "break-all" }}>
        {name}
        {info.internal && <Chip size="small" label="internal" sx={{ ml: 0.5, height: 16, fontSize: 10 }} />}
        <Typography variant="caption" display="block" color="text.secondary">
          {[info.role, info.desc].filter(Boolean).join(": ")}
        </Typography>
      </TableCell>
      <TableCell sx={{ ...cell, wordBreak: "break-all" }}>
        {pv.initialized ? `${array ? [pv.value].flat().join(", ") : pv.value} ${pv.metadata.units ?? ""}` : "no connection"}
      </TableCell>
      <TableCell sx={cell}>{stateNames[state]}</TableCell>
      <TableCell sx={cell}>{stat.initialized ? statusName(stat.value) : ""}</TableCell>
      <TableCell sx={cell}>{formatTime(pv.timestamp)}</TableCell>
    </TableRow>
  );
};

const Fact = ({ label, children }) => (
  <Typography variant="body2" component="div">
    <Typography component="span" variant="body2" color="text.secondary">
      {label}:{" "}
    </Typography>
    {children}
  </Typography>
);

// The expert part of a device window (brief, requirement 7): identity, IOC,
// simulators, the registry's flags and notes, and every record of the device.
const ExpertView = ({ id }) => {
  const device = devices[id];
  const roles = rolesOf(id);
  const ioc = iocOf(id);
  const notes = pvsOf(id).filter((name) => pvInfo(name).note);
  return (
    <Stack spacing={1.5}>
      <Stack spacing={0.5}>
        {["id", "firmware", "channel_list"]
          .filter((role) => roles[role])
          .map((role) => (
            <Fact key={role} label={roleText(id, role)}>
              <PvText pv={roles[role]} field={isLongString(roles[role]) ? "VAL$" : undefined} />
            </Fact>
          ))}
        <Fact label="model">{device.model}</Fact>
        <Fact label="IOC">
          {ioc.name} ({ioc.container}, {ioc.st_cmd})
        </Fact>
        <Fact label="registry">
          id {id}, class {device.class ?? "none"}, page {device.page}, status {device.status}
        </Fact>
        {device.simulators.map((sim) => {
          const s = simulators[sim.split(":")[0]];
          return (
            <Fact key={sim} label="simulator">
              {sim} ({s.type}, {s.host}:{s.port}, asyn port {s.asyn_port})
            </Fact>
          );
        })}
        {Object.entries(device.flags).map(([flag, reason]) => (
          <Fact key={flag} label={`flag ${flag}`}>
            {reason}
          </Fact>
        ))}
        {notes.map((name) => (
          <Fact key={name} label={`note ${name}`}>
            {pvInfo(name).note}
          </Fact>
        ))}
      </Stack>
      <Table size="small" stickyHeader>
        <TableHead>
          <TableRow>
            {["record", "value", "SEVR", "STAT", "time"].map((head) => (
              <TableCell key={head} sx={{ px: 0.5, fontSize: 12 }}>
                {head}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {pvsOf(id).map((name) => (
            <RecordRow key={name} name={name} />
          ))}
        </TableBody>
      </Table>
    </Stack>
  );
};

export default ExpertView;
