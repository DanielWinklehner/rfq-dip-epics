// Device windows (owner's decision at G2): one browser window per device,
// brought to the front when it is open already, closed with the main window.
const open = new Map();

const deviceUrl = (id, channel) => `/device/${id}${channel ? `?channel=${channel}` : ""}`;

export const openDeviceWindow = (id, channel) => {
  const existing = open.get(id);
  if (existing && !existing.closed) {
    existing.focus();
    return;
  }
  open.set(id, window.open(deviceUrl(id, channel), `mist2-${id}`, "popup,width=480,height=760"));
};

window.addEventListener("pagehide", () => open.forEach((w) => w.close()));
