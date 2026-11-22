// The windows of the GUI: one browser window per device (owner's decision at
// G2) and one per page taken out of the main window (owner's wish of
// 2026-11-22). A window that is open already is brought to the front. They
// all belong to the main window and close with it. A page window keeps its
// devices in the main window's list, so a device opened from there gets the
// same one window as from the main window, and stays when the page goes back.
const owner = window.opener && !window.opener.closed && window.opener.mist2Windows ? window.opener : window;
owner.mist2Windows ??= { devices: new Map(), pages: new Map() };
const { devices, pages } = owner.mist2Windows;

const isOpen = (w) => Boolean(w && !w.closed);

const openOnce = (list, key, url, name, features) => {
  const existing = list.get(key);
  if (isOpen(existing)) {
    existing.focus();
    return;
  }
  list.set(key, window.open(url, name, features));
};

const deviceUrl = (id, channel) => `/device/${id}${channel ? `?channel=${channel}` : ""}`;

export const openDeviceWindow = (id, channel) =>
  openOnce(devices, id, deviceUrl(id, channel), `mist2-${id}`, "popup,width=480,height=760");

// A page in a window of its own, or the one it is in brought to the front.
export const openPageWindow = (slug) =>
  openOnce(pages, slug, `/page/${slug}`, `mist2-page-${slug}`, "popup,width=1600,height=1000");

export const isPageOut = (slug) => isOpen(pages.get(slug));

// Back to the main window: a page window closes itself (the main window sees
// it closed and shows the page again); one opened by its address, which a
// script may not close, becomes the main window on that tab.
export const attachPage = (slug) => {
  if (owner !== window) window.close();
  else window.location.assign(`/?tab=${slug}`);
};

if (owner === window) {
  window.addEventListener("pagehide", () => [...devices.values(), ...pages.values()].forEach((w) => w?.close()));
}
