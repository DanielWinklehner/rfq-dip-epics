// Browser side of tools/gui-check.sh: one phase per run, in a headless
// Chromium (Playwright). Reads the GUI through the data attributes its widgets
// carry (data-pv, data-alarm, data-value, data-tab, data-banner, data-ioc).
//
// usage: node gui-check.mjs <phase> <url> <work dir> <screenshot dir> <registry.json> [args]
//   normal               every page and device window: no console problems, live
//                        values, baseline alarm states, the window behaviour;
//                        writes <work>/normal.json (expert values, baseline)
//   fault <spec>...      silent simulators (name or name:unit): their PVs show
//                        INVALID, the tabs the worst state, everything else as before
//   recovered            everything as in the baseline again
//   iocdown <ioc>        the IOC's PVs show "no connection", the banner says so
//   setpoint <id> <role> type the middle of the test range, Enter; prints the value
//   command <id> <channel|-> <role> <value> <dialog|nodialog>
//                        press a request button; the confirmation must (not) appear
//   alloff               press ALL HV OFF in the app bar
// Prints PASS/FAIL lines; exit code 1 on any FAIL.
import fs from "node:fs";
import { chromium } from "playwright";

const [phase, base, work, shots, registryPath, ...args] = process.argv.slice(2);
const registry = JSON.parse(fs.readFileSync(registryPath, "utf8"));
const devices = registry.devices;
const slug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
const installed = Object.keys(devices).filter((id) => !devices[id].flags.not_installed);
const tabs = ["Overview", ...new Set(installed.map((id) => devices[id].page)), "Trends", "Infrastructure"].map(slug);

let failures = 0;
const fail = (message) => {
  failures += 1;
  console.log(`FAIL ${message}`);
};
const pass = (message) => console.log(`PASS ${message}`);
const check = (ok, message) => (ok ? pass(message) : fail(message));

// Console errors and warnings of the GUI. Allowed: the Google sign-in script
// that RAS loads from the internet (no network in the lab), and Vite's notice
// that it re-bundled a dependency (development server only).
const allowed = [/accounts\.google\.com/, /Outdated Optimize Dep/];
const problems = [];
const watch = (page) => {
  page.on("console", (message) => {
    if (!["error", "warning"].includes(message.type())) return;
    const text = `${message.text()} ${message.location().url ?? ""}`;
    if (!allowed.some((pattern) => pattern.test(text))) {
      problems.push(`${page.url()}: console ${message.type()}: ${message.text().slice(0, 400)}`);
    }
  });
  page.on("pageerror", (error) => problems.push(`${page.url()}: ${error.message}`));
};

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
context.on("page", watch);

// Every element that shows a PV: { pv, alarm, text, part, visible, row }.
const collect = (page) =>
  page.evaluate(() =>
    [...document.querySelectorAll("[data-pv]")].map((el) => ({
      pv: el.dataset.pv,
      alarm: el.dataset.alarm,
      text:
        el.tagName === "INPUT"
          ? el.value
          : el.tagName === "TR"
            ? null
            : (el.querySelector("[data-value]")?.textContent.trim() ?? null),
      row: el.tagName === "TR" ? [...el.cells].map((cell) => cell.innerText.trim()) : null,
      part: el.closest("[data-part]")?.dataset.part ?? null,
      visible: el.getClientRects().length > 0,
    }))
  );

const tabStates = (page) =>
  page.evaluate(() =>
    Object.fromEntries(
      [...document.querySelectorAll("[data-tab]")].map((el) => [el.dataset.tab, el.querySelector("[data-alarm]")?.dataset.alarm])
    )
  );

// Waits until the visible elements are connected (or `until` holds).
const settle = async (page, until = (els) => els.every((el) => el.alarm !== "disconnected"), seconds = 20) => {
  const deadline = Date.now() + seconds * 1000;
  let els = [];
  while (Date.now() < deadline) {
    els = (await collect(page)).filter((el) => el.visible || el.part);
    if (els.length > 0 && until(els)) return els;
    await page.waitForTimeout(500);
  }
  return els;
};

// Loads a route; a second try if the application has not rendered in 30 s
// (the development server can be slow while it re-bundles).
const open = async (path, viewport) => {
  const page = await context.newPage();
  if (viewport) await page.setViewportSize(viewport);
  for (let attempt = 1; ; attempt += 1) {
    await page.goto(`${base}${path}`);
    try {
      await page.waitForSelector("[data-banner]");
      return page;
    } catch (error) {
      if (attempt === 2) throw error;
      console.log(`note: ${path} did not render within 30 s, loading it again`);
    }
  }
};
const openMain = (tab) => open(`/?tab=${tab}`);
const openDevice = (id) => open(`/device/${id}`, { width: 480, height: 760 });

const shot = (page, name, fullPage = true) => page.screenshot({ path: `${shots}/${name}.png`, fullPage });

// A value field whose record is INVALID shows the word, not the number.
const checkWords = (els, where) => {
  const wrong = els.filter((el) => el.alarm === "invalid" && el.text !== null && el.text !== "INVALID");
  check(wrong.length === 0, `${where}: every INVALID value shows the word INVALID${wrong.length ? ` (not: ${wrong.map((el) => el.pv).join(", ")})` : ""}`);
};

const stateMap = (els) => Object.fromEntries(els.filter((el) => el.visible && !el.row).map((el) => [el.pv, el.alarm]));

// Every PV each device window must show: the records of the device that are
// not internal.
const expected = (id) => Object.keys(devices[id].pvs).filter((name) => !devices[id].pvs[name].internal);

const faultSpecs = (specs) => {
  // A whole simulator silences its units too; one unit only its own records.
  const hit = (list = []) =>
    specs.some((spec) => list.some((entry) => entry === spec || (!spec.includes(":") && entry.split(":")[0] === spec)));
  return new Set(
    Object.values(devices).flatMap((device) =>
      Object.entries(device.pvs)
        .filter(([, info]) => !info.internal && hit(info.fails_with))
        .map(([name]) => name)
    )
  );
};

// The main pages against the baseline: the PVs in `changed` must be in state
// `state`, every other one as before; each tab dot the worst it shows.
const comparePages = async (label, changed, state, extra = async () => {}) => {
  const baseline = JSON.parse(fs.readFileSync(`${work}/normal.json`, "utf8")).baseline;
  const touched = new Set();
  let dots = {};
  for (const tab of tabs.filter((t) => t !== "trends")) {
    const page = await openMain(tab);
    const els = await settle(page, (all) =>
      all.filter((el) => el.visible).every((el) => (changed.has(el.pv) ? el.alarm === state : el.alarm !== "disconnected"))
    );
    const now = stateMap(els);
    const wrong = Object.entries(now).filter(
      ([pv, alarm]) => alarm !== (changed.has(pv) ? state : (baseline.pages[tab]?.[pv] ?? alarm))
    );
    if (Object.keys(now).some((pv) => changed.has(pv))) touched.add(tab);
    check(
      wrong.length === 0,
      `${label}, ${tab}: ${Object.keys(now).length} PVs, the affected ones ${state}, the others as before${
        wrong.length ? ` (wrong: ${wrong.map(([pv, a]) => `${pv}=${a}`).join(", ")})` : ""
      }`
    );
    checkWords(els, `${label}, ${tab}`);
    dots = await tabStates(page);
    await extra(page, tab);
    await page.close();
  }
  for (const tab of Object.keys(baseline.tabs)) {
    const want = touched.has(tab) ? state : baseline.tabs[tab];
    check(dots[tab] === want, `${label}: tab ${tab} shows ${dots[tab]}, expected ${want}`);
  }
};

const phases = {
  async normal() {
    const baseline = { pages: {}, tabs: {} };
    for (const tab of tabs) {
      const page = await openMain(tab);
      const els = await settle(page);
      const visible = els.filter((el) => el.visible);
      if (tab !== "trends") {
        check(visible.length > 0 && visible.every((el) => el.alarm !== "disconnected"), `${tab}: ${visible.length} PVs, all connected`);
      }
      checkWords(els, tab);
      baseline.pages[tab] = stateMap(els);
      if (tab === "overview") {
        baseline.tabs = await tabStates(page);
        check((await page.title()).startsWith("[SIM] "), `window title "${await page.title()}" starts with [SIM]`);
        const banner = await page.locator("[data-banner]").innerText();
        check(banner.startsWith("EMULATOR"), `emulator banner: ${banner}`);
      }
      if (tab === "trends") {
        await page.getByLabel("Trend these read-backs").click();
        await page.getByRole("option").first().click();
        await page.keyboard.press("Escape");
        await page.waitForTimeout(3000);
        check((await page.locator("[data-trend] .main-svg").count()) > 0, "trends: a picked read-back is drawn");
      }
      await shot(page, `normal-${tab}`, tab !== "overview");
      await page.close();
    }

    const expert = {};
    for (const id of Object.keys(devices)) {
      const page = await openDevice(id);
      const els = await settle(page, (all) => all.filter((el) => el.row).every((el) => el.row[1] !== "no connection"));
      const shown = new Set(els.map((el) => el.pv));
      const missing = expected(id).filter((pv) => !shown.has(pv));
      check(missing.length === 0, `device window ${id}: shows all ${expected(id).length} PVs of the device${missing.length ? ` (missing: ${missing.join(", ")})` : ""}`);
      const controls = els.filter((el) => el.part === "Controls");
      check(
        controls.every((el) => el.alarm !== "disconnected"),
        `device window ${id}: ${controls.length} controls, all connected`
      );
      checkWords(els, `device window ${id}`);
      for (const el of els.filter((e) => e.row)) expert[el.pv] = { value: el.row[1], sevr: el.row[2] };
      await shot(page, `normal-device-${id}`, false);
      if (id === "valves" || id === "au_src") {
        await page.getByRole("tab", { name: "Expert" }).click();
        await shot(page, `normal-device-${id}-expert`);
        await page.getByRole("tab", { name: "Trend" }).click();
        await page.waitForTimeout(2000);
        await shot(page, `normal-device-${id}-trend`, false);
      }
      await page.close();
    }
    fs.writeFileSync(`${work}/normal.json`, JSON.stringify({ baseline, expert }, null, 1));

    // Window behaviour: a click opens the device's window, a second click does
    // not open another, a reload of the main window closes its windows.
    const main = await openMain("overview");
    await settle(main);
    const clickTag = (id) => main.locator(`g[data-device="${id}"]`).first().click({ position: { x: 20, y: 8 } });
    const [first] = await Promise.all([context.waitForEvent("page"), clickTag("turbo1")]);
    await first.waitForLoadState();
    check(first.url().endsWith("/device/turbo1"), `click on the Turbopump 1 tag opens ${first.url()}`);
    const before = context.pages().length;
    await clickTag("turbo1");
    await main.waitForTimeout(1500);
    check(context.pages().length === before, "a second click on it opens no second window");
    const [second] = await Promise.all([context.waitForEvent("page"), clickTag("naim")]);
    await second.waitForLoadState();
    check(context.pages().length === before + 1, "another device opens a window of its own beside it");
    await main.reload();
    await main.waitForTimeout(1500);
    check(first.isClosed() && second.isClosed(), "a reload of the main window closes the device windows");
    await main.close();
  },

  async fault() {
    const changed = faultSpecs(args);
    await comparePages(`silent ${args.join(" ")}`, changed, "invalid", async (page, tab) => {
      if (["overview", "plasma-generator", "extraction"].includes(tab)) await shot(page, `fault-${tab}`, tab !== "overview");
    });
    const ids = installed.filter((id) => expected(id).some((pv) => changed.has(pv)));
    for (const id of ids) {
      const page = await openDevice(id);
      const els = await settle(page, (all) => all.filter((el) => changed.has(el.pv)).every((el) => el.alarm === "invalid"));
      const controls = els.filter((el) => el.part === "Controls" && changed.has(el.pv));
      check(
        controls.length > 0 && controls.every((el) => el.alarm === "invalid"),
        `device window ${id}: its ${controls.length} affected controls show INVALID`
      );
      checkWords(els, `device window ${id}`);
      await shot(page, `fault-device-${id}`, false);
      await page.close();
    }
  },

  async recovered() {
    await comparePages("after clearing", new Set(), "ok");
  },

  async iocdown() {
    const [ioc] = args;
    const changed = new Set(installed.filter((id) => devices[id].ioc === ioc).flatMap(expected));
    await comparePages(`${ioc} stopped`, changed, "disconnected", async (page, tab) => {
      if (tab === "overview") {
        const banner = await page.locator("[data-banner]").innerText();
        check(banner.includes("mode unknown"), `banner with the IOC stopped: ${banner}`);
        const chip = await page.locator(`div[data-ioc="${ioc}"]`).getAttribute("data-alarm");
        check(chip === "disconnected", `IOC chip of ${ioc}: ${chip}`);
        await shot(page, "iocdown-overview", false);
      }
      if (tab === "plasma-generator") await shot(page, "iocdown-plasma-generator");
    });
    const id = installed.find((d) => devices[d].ioc === ioc);
    const page = await openDevice(id);
    await page.waitForTimeout(3000);
    await shot(page, `iocdown-device-${id}`, false);
    await page.close();
  },

  async setpoint() {
    const [id, role] = args;
    const pv = devices[id].roles[role];
    const [low, high] = devices[id].pvs[pv].test;
    const value = Number(((low + high) / 2 + (high - low) * 0.1).toFixed(2));
    const page = await openDevice(id);
    await settle(page);
    const input = page.locator(`input[data-pv="${pv}"]`);
    await input.fill(String(value));
    await input.press("Enter");
    await page.waitForTimeout(1000);
    await input.blur();
    await shot(page, `write-setpoint-${id}`, false);
    await page.close();
    fs.writeFileSync(`${work}/setpoint.txt`, `${devices[id].pvs[pv].readback} ${value}\n`);
    pass(`typed ${value} into ${id} ${role} and pressed Enter`);
  },

  async command() {
    const [id, channel, role, value, dialog] = args;
    const roles = channel === "-" ? devices[id].roles : devices[id].channels[channel].roles;
    const page = await openDevice(id);
    await settle(page);
    const group = page.locator(`[data-part="Controls"] [data-pv="${roles[role]}"]`);
    await group.getByRole("button").nth(Number(value)).click();
    const shown = await page
      .getByRole("dialog")
      .waitFor({ state: "visible", timeout: 2000 })
      .then(() => true)
      .catch(() => false);
    check(shown === (dialog === "dialog"), `${id} ${channel} ${role} := ${value}: ${shown ? "asks" : "does not ask"} for confirmation`);
    if (shown) {
      await shot(page, `write-confirm-${id}-${channel}`, false);
      await page.getByRole("dialog").getByRole("button").last().click();
    }
    await page.waitForTimeout(1000);
    await page.close();
  },

  async alloff() {
    const page = await openMain("extraction");
    await settle(page);
    await page.locator("header button", { hasText: "ALL HV OFF" }).click();
    await page.waitForTimeout(1500);
    await shot(page, "write-after-all-hv-off");
    await page.close();
    pass("pressed ALL HV OFF in the app bar");
  },
};

try {
  await phases[phase]();
} catch (error) {
  fail(`${phase}: ${error.message.split("\n")[0]}`);
}
await browser.close();
check(problems.length === 0, `no JavaScript error or warning (${phase})${problems.length ? `:\n  ${problems.join("\n  ")}` : ""}`);
process.exit(failures ? 1 : 0);
