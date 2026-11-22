import React from "react";
import Link from "@mui/material/Link";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { AlarmChip } from "../alarm/AlarmMarks";
import { useWorstAlarm } from "../alarm/AlarmStore";
import { widgetOf } from "../components/devices";
import { flagTitles } from "../components/Flags";
import PvText from "../components/fields/PvText";
import { alarmPvs, devices, infrastructureDevices, iocOf, iocs, isLongString, rolesOf } from "../registry";
import { openDeviceWindow } from "../windows";

const identityRoles = ["id", "firmware", "channel_list"];

const DeviceRow = ({ id }) => {
  const device = devices[id];
  const state = useWorstAlarm(alarmPvs(id));
  const roles = rolesOf(id);
  return (
    <TableRow data-device={id}>
      <TableCell>
        <Link component="button" variant="body2" onClick={() => openDeviceWindow(id)}>
          {device.name}
        </Link>
        <Typography variant="caption" display="block" color="text.secondary">
          {id} · {device.model}
        </Typography>
      </TableCell>
      <TableCell>{device.class ?? "none"}</TableCell>
      <TableCell>{device.page ?? "none: infrastructure"}</TableCell>
      <TableCell>{iocOf(id).name}</TableCell>
      <TableCell>{alarmPvs(id).length > 0 && <AlarmChip state={state} />}</TableCell>
      {identityRoles.map((role) => (
        <TableCell key={role}>
          {roles[role] && <PvText pv={roles[role]} field={isLongString(roles[role]) ? "VAL$" : undefined} />}
        </TableCell>
      ))}
      <TableCell>
        {Object.entries(device.flags).map(([flag, reason]) => (
          <Typography key={flag} variant="caption" display="block" data-flag={flag}>
            <strong>{flagTitles[flag] ?? flag}:</strong> {reason}
          </Typography>
        ))}
      </TableCell>
    </TableRow>
  );
};

// A service of the control system (a device whose subsystem has no page):
// here only, with its widget.
const Service = ({ id }) => {
  const DeviceWidget = widgetOf(devices[id].class);
  return (
    <Paper variant="outlined" sx={{ p: 1.5, width: 480 }} data-service-card={id}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
        <Link component="button" variant="subtitle1" onClick={() => openDeviceWindow(id)}>
          {devices[id].name}
        </Link>
        <AlarmChip state={useWorstAlarm(alarmPvs(id))} />
      </Stack>
      <DeviceWidget id={id} />
    </Paper>
  );
};

// The services of the control system, then every IOC and every device of the
// registry, installed or not, with its identity and the state of its
// communication.
const InfrastructurePage = () => (
  <Stack spacing={2} sx={{ p: 1 }}>
    <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
      {infrastructureDevices.map((id) => (
        <Service key={id} id={id} />
      ))}
    </Stack>
    <Paper variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            {["IOC", "container", "st.cmd", "heartbeat", "mode"].map((head) => (
              <TableCell key={head}>{head}</TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {Object.entries(iocs).map(([id, ioc]) => (
            <TableRow key={id} data-ioc={id}>
              <TableCell>{ioc.name}</TableCell>
              <TableCell>{ioc.container}</TableCell>
              <TableCell>{ioc.st_cmd}</TableCell>
              <TableCell>
                <PvText pv={ioc.roles.heartbeat} />
              </TableCell>
              <TableCell>
                <PvText pv={ioc.roles.mode} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Paper>
    <Paper variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            {["device", "class", "page", "IOC", "communication", "name", "firmware", "channels", "flags"].map(
              (head) => (
                <TableCell key={head}>{head}</TableCell>
              )
            )}
          </TableRow>
        </TableHead>
        <TableBody>
          {Object.keys(devices).map((id) => (
            <DeviceRow key={id} id={id} />
          ))}
        </TableBody>
      </Table>
    </Paper>
  </Stack>
);

export default InfrastructurePage;
