import { roleLabel } from "./registry";

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

export const roleText = (id, role) => roleLabel(id, role) ?? roleWords[role] ?? role;

// Read-back roles that are drawn as a trend: on the subsystem pages, in the
// device windows and in the choice of the Trends page. Pressures on a log scale.
export const trendRoles = ["vread", "iread", "value", "p", "speed", "current", "flow"];
export const logScaleRoles = ["p"];
