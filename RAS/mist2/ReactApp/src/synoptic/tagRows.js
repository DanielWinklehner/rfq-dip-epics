import { channelClass, channelLabel, connectedChannels, devices, pvInfo, rolesOf, wordsOf } from "../registry";
import { roleText } from "../roles";

// The tag form of each widget class (LAYOUT.md 1.4): the roles a tag reads.
// A class not listed (a controller of other devices) shows its identity.
const tagRoles = {
  supply: ["vread", "iread", "out_state"],
  valve: ["state"],
  gauge: ["p", "result"],
  turbo: ["state", "speed", "result"],
  mfc: ["flow", "sp"],
  reading: ["value"],
  interlock: ["open", "state"],
  command: [],
  loop: ["mode", "pv", "reason"],
};

// What the operator sets in a tag, in place (owner's wish of 2026-11-22): the
// set points and requests of the widget's operation group. Saved settings
// (current limits, the loop's gains, limits and times) stay in the device
// window. Only roles the registry has as written records are set; a request
// with `confirm` in the registry asks first, as in the device window.
const setRoles = {
  supply: ["vset", "iset", "out_cmd"],
  valve: ["cmd"],
  gauge: ["enable"],
  turbo: ["run_cmd"],
  mfc: ["sp_cmd"],
  loop: ["mode_cmd", "sp_cmd"],
};

// A read role whose value can be INVALID or out of range for a reason the
// device states in its role `state`: the tag shows the state's word beside the
// value while the value is not in alarm-free state (a gauge: "Off", "Striking",
// "Gauge Not connected", "Underrange").
const stateBeside = { gauge: "p" };

// Rows of a tag: { pv, words, label } for what it reads, then { set: true,
// pv, id, channel, role, label } for what it sets. A tag of one channel shows
// that channel; a tag of a device shows the device's roles, then every
// connected channel (spare ones only in the device window).
const tagRows = (id, channel) => {
  const rowsOf = (ch, label) => {
    // a channel with a class of its own (the pumps of the TIC station) is shown as that class
    const kind = (ch && channelClass(id, ch)) ?? devices[id].class;
    const reads = tagRoles[kind] ?? ["id"];
    const sets = setRoles[kind] ?? [];
    const roles = rolesOf(id, ch);
    const read = reads.filter((role) => roles[role]);
    const set = sets.filter((role) => roles[role] && pvInfo(roles[role]).access === "w");
    const rowLabel = (role) =>
      label && read.length + set.length === 1 ? label : [label, roleText(id, role)].filter(Boolean).join(" ");
    return [
      ...read.map((role) => ({
        pv: roles[role],
        words: wordsOf(id, ch, role),
        label: rowLabel(role),
        ...(stateBeside[kind] === role && roles.state
          ? { statePv: roles.state, stateWords: wordsOf(id, ch, "state") }
          : {}),
      })),
      ...set.map((role) => ({ set: true, pv: roles[role], id, channel: ch, role, label: rowLabel(role) })),
    ];
  };
  if (channel) return rowsOf(channel);
  return [
    ...rowsOf(undefined),
    ...connectedChannels(id).flatMap((ch) => rowsOf(ch, channelLabel(id, ch) ?? ch)),
  ];
};

export default tagRows;
