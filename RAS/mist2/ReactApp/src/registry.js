import registry from "./registry/registry.json";

// The only door to the device registry (registry/README.md). Everything the
// GUI knows about IOCs, devices, PVs, roles, labels and flags comes through
// these functions.

export const iocs = registry.iocs;
export const devices = registry.devices;
export const simulators = registry.simulators;

const allPvs = Object.fromEntries([
  ...Object.values(iocs).flatMap((ioc) => Object.entries(ioc.pvs)),
  ...Object.values(devices).flatMap((device) => Object.entries(device.pvs)),
]);

export const pvInfo = (name) => allPvs[name];

const owners = Object.fromEntries(
  Object.entries(devices).flatMap(([id, device]) => Object.keys(device.pvs).map((name) => [name, id]))
);
export const deviceOfPv = (name) => owners[name];

const isInstalled = (id) => !devices[id].flags.not_installed;

// Installed devices in registry order, optionally of one page.
export const installedDevices = (page) =>
  Object.keys(devices).filter(
    (id) => isInstalled(id) && (page === undefined || devices[id].page === page)
  );

// The subsystem pages, in the order their first device appears in the registry.
export const subsystemPages = [...new Set(installedDevices().map((id) => devices[id].page))];

// Record types whose value is a text: the state strings of binary and
// multi-bit records, and string records.
const textTypes = ["bi", "bo", "mbbi", "mbbo", "stringin", "stringout", "lsi", "lso"];
export const isText = (name) => textTypes.includes(pvInfo(name).type);
export const isLongString = (name) => ["lsi", "lso"].includes(pvInfo(name).type);

// Roles of a device, or of one of its channels: { role: PV name }.
export const rolesOf = (id, channel) =>
  channel ? devices[id].channels[channel].roles : devices[id].roles;

export const channelsOf = (id) => Object.keys(devices[id].channels ?? {});

// A spare channel is not connected: it is shown only in the device window.
export const isSpare = (id, channel) => Boolean(devices[id].channels[channel].spare);
export const connectedChannels = (id) => channelsOf(id).filter((channel) => !isSpare(id, channel));

export const channelLabel = (id, channel) => devices[id].channels[channel].label;

// The words of a role's values (index = value): those of the channel, else
// the device's words for the role, else the record's own state strings.
export const wordsOf = (id, channel, role) =>
  (channel ? devices[id].channels[channel].states : devices[id].states?.[role]) ??
  pvInfo(rolesOf(id, channel)[role]).states;

// The label of a device-level role, if the registry has one.
export const roleLabel = (id, role) => devices[id].labels?.[role];

// The records whose severity says whether a device, or one channel of it, is
// healthy: every read PV that is not internal and not of a spare channel.
export const alarmPvs = (id, channel) => {
  const names = channel ? Object.values(rolesOf(id, channel)) : Object.keys(devices[id].pvs);
  return names.filter((name) => {
    const info = pvInfo(name);
    return info.access === "r" && !info.internal && !(info.channel && isSpare(id, info.channel));
  });
};

// Every PV of a device in registry order, internal ones included.
export const pvsOf = (id) => Object.keys(devices[id].pvs);

export const iocOf = (id) => iocs[devices[id].ioc];
