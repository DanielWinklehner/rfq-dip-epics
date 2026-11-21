import { channelsOf, isPolled, isText, pvInfo, roleLabel, rolesOf } from "./registry";

// What each registry role means to the operator. Roles are the contract
// between the registry and the widget classes; the registry's own labels win.
const roleWords = {
  vset: "voltage set point",
  vget: "voltage set point echo",
  vread: "voltage read",
  iset: "current set point",
  iget: "current set point echo",
  ilimit: "current limit",
  ilimit_get: "current limit echo",
  iread: "current read",
  power: "power",
  out_cmd: "output request",
  out_state: "output state",
  status: "remote status",
  mode: "mode",
  fault: "fault",
  run_cmd: "run request",
  run_state: "run contact",
  accel: "accel",
  atspeed: "normal",
  failure: "failure",
  state: "state",
  age: "age of the last record",
  raw: "last record",
  speed: "speed",
  current: "current",
  sp_cmd: "set point",
  sp: "set point echo",
  flow: "flow",
  wink_cmd: "wink",
  wink: "wink echo",
  p: "pressure",
  enable: "gauge",
  value: "value",
  junction: "cold junction",
  open: "interlock",
  cmd: "command",
  id: "device name",
  firmware: "firmware",
  channel_list: "channels",
  heartbeat: "heartbeat",
};

export const roleWord = (role) => roleWords[role] ?? role;
export const roleText = (id, role) => roleLabel(id, role) ?? roleWord(role);

// Read-back roles that are drawn as a trend: on the subsystem pages, in the
// device windows and in the choice of the Trends page.
const trendRoles = ["vread", "iread", "value", "p", "speed", "current", "flow"];

// The trend PVs of a device (all its channels) or of one channel.
export const trendPvs = (id, channel) =>
  isPolled(id)
    ? (channel ? [channel] : [undefined, ...channelsOf(id)]).flatMap((ch) =>
        trendRoles.map((role) => rolesOf(id, ch)[role]).filter(Boolean)
      )
    : [];

// Roles whose record is a plain 0/1 number (no state strings) shown as a lamp,
// with the words for 0 and 1 where "off"/"on" would mislead.
export const lampWords = { state: undefined, open: ["closed", "OPEN"] };

// A read-back shown as a lamp: a binary record, or a lamp role without strings.
export const isLamp = (pv, role) =>
  pvInfo(pv).type === "bi" || (role in lampWords && !isText(pv));

// Roles shown in exponent format, and on a log scale in trends.
export const exponentRoles = ["p"];
