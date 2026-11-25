import registry from "./registry/registry.json";

// The only door to the device registry (registry/README.md). Everything the
// GUI knows about IOCs, devices, PVs, roles, labels and flags comes through
// these functions.

export const iocs = registry.iocs;
export const devices = registry.devices;
export const simulators = registry.simulators;

// The PVs of a channel that is not installed (a TIC socket without a gauge)
// are listed apart in the registry (not_installed_pvs): known here, shown in
// the device window, left out of tags, alarms and trends.
const devicePvs = (device) => ({ ...device.pvs, ...(device.not_installed_pvs ?? {}) });

const allPvs = Object.fromEntries([
  ...Object.values(iocs).flatMap((ioc) => Object.entries(ioc.pvs)),
  ...Object.values(devices).flatMap((device) => Object.entries(devicePvs(device))),
]);

export const pvInfo = (name) => allPvs[name];

const owners = Object.fromEntries(
  Object.entries(devices).flatMap(([id, device]) => Object.keys(devicePvs(device)).map((name) => [name, id]))
);
export const deviceOfPv = (name) => owners[name];

const isInstalled = (id) => !devices[id].flags.not_installed;

// Installed devices in registry order, optionally of one page.
export const installedDevices = (page) =>
  Object.keys(devices).filter(
    (id) => isInstalled(id) && (page === undefined || devices[id].page === page)
  );

// A device whose subsystem has no page is infrastructure (the services of the
// control system, such as the data logger): on the Infrastructure page only.
export const isInfrastructure = (id) => !devices[id].page;
export const infrastructureDevices = installedDevices().filter(isInfrastructure);

// The installed devices that the drawings show: all but the infrastructure.
export const drawnDevices = installedDevices().filter((id) => !isInfrastructure(id));

// The subsystem pages, in the order their first device appears in the registry.
export const subsystemPages = [...new Set(drawnDevices.map((id) => devices[id].page))];

// The read-back roles drawn as a trend, and the set points drawn in the graph
// of their read-back ({ read-back role: set point role }); the logger's
// dashboards read the same list (plan, `trends`).
export const trends = registry.trends;

// Record types whose value is a text: the state strings of binary and
// multi-bit records, and string records.
const textTypes = ["bi", "bo", "mbbi", "mbbo", "stringin", "stringout", "lsi", "lso"];
export const isText = (name) => textTypes.includes(pvInfo(name).type);
export const isLongString = (name) => ["lsi", "lso"].includes(pvInfo(name).type);

// A channel of a device: installed ones under `channels`, those flagged not
// installed (plan: channel_flags) under `not_installed_channels`.
const channelOf = (id, channel) =>
  devices[id].channels?.[channel] ?? devices[id].not_installed_channels[channel];

// Roles of a device, or of one of its channels: { role: PV name }.
export const rolesOf = (id, channel) => (channel ? channelOf(id, channel).roles : devices[id].roles);

// Every channel, the ones not installed last (the device window lists them).
export const channelsOf = (id) => [
  ...Object.keys(devices[id].channels ?? {}),
  ...Object.keys(devices[id].not_installed_channels ?? {}),
];

// A spare channel is not connected: it is shown only in the device window.
export const isSpare = (id, channel) => Boolean(channelOf(id, channel).spare);
// A channel flagged not installed (plan: channel_flags) is treated as a device
// that is not installed: only in the device window, never in a tag or alarm.
export const isChannelInstalled = (id, channel) => !channelOf(id, channel).flags?.not_installed;
export const channelFlags = (id, channel) => channelOf(id, channel).flags ?? {};
export const connectedChannels = (id) =>
  channelsOf(id).filter((channel) => !isSpare(id, channel) && isChannelInstalled(id, channel));

export const channelLabel = (id, channel) => channelOf(id, channel).label;

// The words of a role's values (index = value): those of the channel, else
// the device's words for the role, else the record's own state strings.
export const wordsOf = (id, channel, role) =>
  (channel ? channelOf(id, channel).states : devices[id].states?.[role]) ??
  pvInfo(rolesOf(id, channel)[role]).states;

// The label of a device-level role, if the registry has one.
export const roleLabel = (id, role) => devices[id].labels?.[role];

// The records whose severity says whether a device, or one channel of it, is
// healthy: every read PV that is not internal and not of a spare channel.
export const alarmPvs = (id, channel) => {
  const names = channel ? Object.values(rolesOf(id, channel)) : Object.keys(devices[id].pvs);
  return names.filter((name) => {
    const info = pvInfo(name);
    return (
      info.access === "r" &&
      !info.internal &&
      !(info.channel && (isSpare(id, info.channel) || !isChannelInstalled(id, info.channel)))
    );
  });
};

// Every PV of a device in registry order, internal ones included.
export const pvsOf = (id) => Object.keys(devices[id].pvs);

export const iocOf = (id) => iocs[devices[id].ioc];
