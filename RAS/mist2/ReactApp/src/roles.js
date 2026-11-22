import { connectedChannels, roleLabel, rolesOf } from "./registry";

// What each registry role means to the operator. Roles are the contract
// between the registry and the widget classes; the registry's own labels win.
const roleWords = {
  vset: "voltage set point",
  vget: "voltage set point echo",
  vread: "voltage read",
  iset: "current set point",
  ilimit: "current limit",
  ilimit_get: "current limit echo",
  iread: "current read",
  power: "power",
  out_cmd: "output request",
  out_state: "output state",
  status: "status",
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
  // The control loop (docs/emulation/LOOP.md section 3).
  mode_cmd: "mode request",
  reason: "hand-back / refusal",
  service: "loop service",
  permit1: "permit 1",
  permit2: "permit 2",
  permit3: "permit 3",
  limit: "output at a limit",
  pv: "measured value",
  out: "output",
  error: "error",
  pterm: "P term",
  iterm: "I term",
  dterm: "D term",
  spmin: "set point minimum",
  spmax: "set point maximum",
  kp: "Kp, proportional gain",
  ki: "Ki, integral gain",
  kd: "Kd, derivative gain",
  dfilter: "derivative filter time",
  outmin: "output minimum",
  outmax: "output maximum",
  slew: "output slew limit",
  stale: "stale after",
  watchdog: "watchdog time",
};

export const roleWord = (role) => roleWords[role] ?? role;
export const roleText = (id, role) => roleLabel(id, role) ?? roleWord(role);

// Read-back roles that are drawn as a trend: on the subsystem pages, in the
// device windows and in the choice of the Trends page.
const trendRoles = ["vread", "iread", "value", "p", "speed", "current", "flow", "pv", "out"];

// A set point drawn in the graph of the read-back it is for (the loop's set
// point with its measured value), where the device has both.
const trendBeside = { pv: "sp_cmd" };
export const trendGraph = (role) =>
  Object.keys(trendBeside).find((graph) => trendBeside[graph] === role) ?? role;

// The trend PVs of a device (its connected channels too) or of one channel.
export const trendPvs = (id, channel) =>
  (channel ? [channel] : [undefined, ...connectedChannels(id)]).flatMap((ch) => {
    const roles = rolesOf(id, ch);
    return trendRoles
      .filter((role) => roles[role])
      .flatMap((role) => [roles[role], roles[trendBeside[role]]])
      .filter(Boolean);
  });
