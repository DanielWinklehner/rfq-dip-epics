import { channelClass, connectedChannels, roleLabel, rolesOf, trends } from "./registry";

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
  // The TIC station's requests and its gauge's slave setup (T32).
  enable_state: "gauge on (controller)",
  result: "last request",
  slave: "switched by its controller",
  slave_on: "controller switches on at",
  slave_off: "controller switches off above",
  slave_master: "slave master object",
  slave_raw: "slave setup reply",
  type: "type",
  alert: "alert",
  units: "units",
  priority: "priority",
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
  // The data logger's state (docs/emulation/LOGGER.md section 6).
  alive: "alive",
  db: "database",
  connected: "PVs connected",
  disconnected: "PVs not connected",
  rows: "rows written",
  buffer: "buffer in use",
  dropped: "rows lost",
  count: "counter",
};

export const roleWord = (role) => roleWords[role] ?? role;

// Words for the roles of a channel shown with another class's widget (the
// pumps of the TIC station, T32): their read-back is the state the station
// reports, not a relay contact as for the big turbopump.
const classChannelWords = {
  run_state: "run state (station)",
};

export const roleText = (id, role, channel) =>
  roleLabel(id, role) ??
  (channel && channelClass(id, channel) ? classChannelWords[role] : undefined) ??
  roleWord(role);

// The trend PVs of a device (its connected channels too) or of one channel:
// the registry's trend roles, each with the set point drawn beside it where
// the device has both.
export const trendGraph = (role) =>
  Object.keys(trends.beside).find((graph) => trends.beside[graph] === role) ?? role;

export const trendPvs = (id, channel) =>
  (channel ? [channel] : [undefined, ...connectedChannels(id)]).flatMap((ch) => {
    const roles = rolesOf(id, ch);
    return trends.roles
      .filter((role) => roles[role])
      .flatMap((role) => [roles[role], roles[trends.beside[role]]])
      .filter(Boolean);
  });
