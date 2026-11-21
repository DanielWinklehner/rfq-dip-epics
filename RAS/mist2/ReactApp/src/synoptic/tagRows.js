import { channelLabel, connectedChannels, devices, rolesOf, wordsOf } from "../registry";
import { roleText } from "../roles";

// The tag form of each widget class (LAYOUT.md 1.4): the roles a tag shows.
// A class not listed (a controller of other devices) shows its identity.
const tagRoles = {
  supply: ["vread", "iread", "out_state"],
  valve: ["state"],
  gauge: ["p"],
  turbo: ["state", "speed"],
  mfc: ["flow", "sp"],
  reading: ["value"],
  interlock: ["open", "state"],
  command: [],
};

// Rows of a tag: { pv, words, label }. A tag of one channel shows that
// channel; a tag of a device shows the device's roles, then every connected
// channel (spare ones only in the device window).
const tagRows = (id, channel) => {
  const roles = tagRoles[devices[id].class] ?? ["id"];
  const rowsOf = (ch, label) => {
    const present = roles.filter((role) => rolesOf(id, ch)[role]);
    return present.map((role) => ({
      pv: rolesOf(id, ch)[role],
      words: wordsOf(id, ch, role),
      label: label && present.length === 1 ? label : [label, roleText(id, role)].filter(Boolean).join(" "),
    }));
  };
  if (channel) return rowsOf(channel);
  return [
    ...rowsOf(undefined),
    ...connectedChannels(id).flatMap((ch) => rowsOf(ch, channelLabel(id, ch) ?? ch)),
  ];
};

export default tagRows;
