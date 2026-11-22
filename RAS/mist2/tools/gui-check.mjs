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
//   recovered [ca.json]  everything as in the baseline again; with a Channel Access
//                        read of the moment (after an IOC start), a record that is
//                        INVALID with status UDF there (not processed since the
//                        start) may show INVALID: it is named in a note
//   iocdown <ioc>        the IOC's PVs show "no connection", the banner says so
//   setpoint <id> <role> type the middle of the test range, Enter; prints the value
//   command <id> <channel|-> <role> <value> <dialog|nodialog>
//                        press a request button; the confirmation must (not) appear
//   alloff               press ALL HV OFF in the app bar
//   shows <id> <role> <value>
//                        the request buttons of a role show that value pressed
//   tagsetpoint <tab> <id> <role> <escape|enter>
//                        in the device's tag on a main page: type a value; escape:
//                        it is marked unsent, Escape shows the IOC's value again;
//                        enter: Enter sends it; prints the value
//   tagcommand <tab> <id> <channel|-> <role> <value> <dialog|nodialog>
//                        press a request button in a tag; the confirmation must
//                        (not) appear, and no device window opens
//   loop <id> refuse     the loop's device window: PID requested, the request
//                        returns to MANUAL and the reason is the first permit
//                        that is not fulfilled, in the window and in the tag
//   loop <id> pid        PID from the loop's tag, the mode shows PID; a set point
//                        typed in the device window; MANUAL again there
//   logger <alive>       each service of the control system (the data logger):
//                        its chip in the strip of the main window, a page window
//                        and its device window shows `alive` as Channel Access
//                        reads it (1: plain, 0: MAJOR); its widget on the
//                        Infrastructure page; on no drawing and in no list area
//   windows <tab>        the page in a window of its own: complete, its values
//                        (<work>/window.json), its tab marked and bringing it to
//                        the front, one window per device from it, "attach" and
//                        the browser's close bring it back, every page out, a
//                        reload of the main window closes them all
// Prints PASS/FAIL lines; exit code 1 on any FAIL.
import fs from "node:fs";
import { chromium } from "playwright";

const [phase, base, work, shots, registryPath, ...args] = process.argv.slice(2);
const registry = JSON.parse(fs.readFileSync(registryPath, "utf8"));
const devices = registry.devices;
const slug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
const installed = Object.keys(devices).filter((id) => !devices[id].flags.not_installed);
// Pages of the main window; a device without a page is infrastructure (Infrastructure page only).
const tabs = ["Overview", ...new Set(installed.map((id) => devices[id].page).filter(Boolean)), "Trends", "Infrastructure"].map(slug);
const services = installed.filter((id) => !devices[id].page && devices[id].roles.alive);

let failures = 0;
const fail = (message) => {
  failures += 1;
  console.log(`FAIL ${message}`);
};
const pass = (message) => console.log(`PASS ${message}`);
const check = (ok, message) => (ok ? pass(message) : fail(message));

// Console errors and warnings of the GUI. Allowed: the Google sign-in script
// that RAS loads from the internet (no network in the lab), Vite's notice
// that it re-bundled a dependency (development server only), and Chromium's
// note that the host's networks changed (Docker networks of other test runs).
const allowed = [/accounts\.google\.com/, /Outdated Optimize Dep/, /net::ERR_NETWORK_CHANGED/];
const problems = [];
const watch = (page) => {
  page.on("console", async (message) => {
    if (!["error", "warning"].includes(message.type())) return;
    const text = `${message.text()} ${message.location().url ?? ""}`;
    if (!allowed.some((pattern) => pattern.test(text))) {
      // The further arguments carry React's component stack, where it gives
      // one, and the JavaScript stack (init script below).
      const args = await Promise.all(message.args().map((arg) => arg.jsonValue().catch(() => "")));
      problems.push(`${page.url()}: console ${message.type()}: ${args.join(" ").slice(0, 4000)}`);
    }
  });
  page.on("pageerror", (error) => problems.push(`${page.url()}: ${error.message}`));
};

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
context.on("page", watch);
// React gives no component stack with some errors ("Maximum update depth
// exceeded" carries the message only), so every console error and warning
// also carries the JavaScript stack of its call: it names the setState caller.
await context.addInitScript(() => {
  for (const level of ["error", "warn"]) {
    const original = console[level].bind(console);
    console[level] = (...args) => original(...args, `\nJS stack: ${new Error().stack}`);
  }
});

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
// A page with trends: they redraw once a second, and one without a value says so after 3 s.
const pageShot = async (page, name, fullPage) => {
  await page.waitForTimeout(4000);
  await shot(page, name, fullPage);
};

// Pairs of tags of a drawing whose boxes overlap on the screen.
const tagOverlaps = (page) =>
  page.evaluate(() => {
    const boxes = [...document.querySelectorAll("svg[data-page] g[data-device]")]
      .filter((g) => g.getClientRects().length > 0)
      .map((g) => [`${g.dataset.device}${g.dataset.channel ? `/${g.dataset.channel}` : ""}`, g.querySelector("rect").getBoundingClientRect()]);
    const hit = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
    return boxes.flatMap(([na, a], i) => boxes.slice(i + 1).filter(([, b]) => hit(a, b)).map(([nb]) => `${na} / ${nb}`));
  });

// The tag of a device (or of one channel) on a page of the main window, which
// keeps its other pages mounted and hidden.
const tagOf = (page, tab, id, channel) =>
  page.locator(
    `[data-page-tab="${tab}"] svg[data-page] g[data-device="${id}"]${channel && channel !== "-" ? `[data-channel="${channel}"]` : ""}`
  );
const rolesOf = (id, channel) => (channel && channel !== "-" ? devices[id].channels[channel].roles : devices[id].roles);

// Polls `read` until `ok` holds; the last value read and the seconds it took.
const until = async (read, ok, seconds) => {
  const start = Date.now();
  let value = await read();
  while (!ok(value) && Date.now() - start < seconds * 1000) {
    await new Promise((resolve) => setTimeout(resolve, 100));
    value = await read();
  }
  return [value, (Date.now() - start) / 1000];
};

// The value between the middle and the top of a set point's test range.
const testValue = (id, role, share) => {
  const [low, high] = devices[id].pvs[devices[id].roles[role]].test;
  return Number(((low + high) / 2 + (high - low) * share).toFixed(2));
};

// What a page shows of each PV in the terms of a Channel Access read, for
// `gui_check_ca.py compare`: a word of the registry as the record's own state
// string (or its index), a number with an SI prefix in the record's unit.
const sevrNames = { ok: "NO_ALARM", minor: "MINOR", major: "MAJOR", invalid: "INVALID" };
const prefixes = { p: 1e-12, n: 1e-9, "µ": 1e-6, m: 1e-3, k: 1e3, M: 1e6 };
const pvInfo = Object.fromEntries(Object.values(devices).flatMap((d) => Object.entries(d.pvs)));
const pvWords = Object.fromEntries(
  Object.values(devices).flatMap((d) => [
    ...Object.entries(d.roles).map(([role, pv]) => [pv, d.states?.[role] ?? d.pvs[pv].states]),
    ...Object.values(d.channels ?? {}).flatMap((c) => Object.values(c.roles).map((pv) => [pv, c.states ?? d.pvs[pv].states])),
  ])
);
const asRead = (pv, text) => {
  const info = pvInfo[pv];
  const bare = text.replace(/ [▲■?×]$/, "");
  const index = pvWords[pv]?.indexOf(bare) ?? -1;
  if (index >= 0) return info.states?.[index] ?? String(index);
  const [number, unit] = bare.split(" ");
  const factor = unit && info.egu && unit !== info.egu && unit.endsWith(info.egu) ? prefixes[unit.slice(0, -info.egu.length)] : undefined;
  return factor && Number.isFinite(Number(number)) ? String(Number(number) * factor) : bare;
};
const shownValues = (els) =>
  Object.fromEntries(
    els
      .filter((el) => el.text !== null && !el.row && el.alarm in sevrNames)
      .map((el) => [el.pv, { value: asRead(el.pv, el.text), sevr: sevrNames[el.alarm] }])
  );

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
// A running logger counts the logged PVs that are not connected: while an IOC
// is stopped, and until it has reconnected after its start, that record of
// the logger may be MINOR (it is OK when no logger runs).
const loggerTolerance = () =>
  Object.fromEntries(services.filter((id) => devices[id].roles.disconnected).map((id) => [devices[id].roles.disconnected, "minor"]));

// `tolerated`: { pv: state } a PV may show besides its baseline state.
const comparePages = async (label, changed, state, extra = async () => {}, tolerated = {}) => {
  const baseline = JSON.parse(fs.readFileSync(`${work}/normal.json`, "utf8")).baseline;
  const touched = new Set();
  const showsTolerated = new Map();
  for (const tab of tabs.filter((t) => t !== "trends")) {
    const page = await openMain(tab);
    const els = await settle(page, (all) =>
      all.filter((el) => el.visible).every((el) => (changed.has(el.pv) ? el.alarm === state : el.alarm !== "disconnected"))
    );
    const now = stateMap(els);
    const wrong = Object.entries(now).filter(
      ([pv, alarm]) =>
        alarm !== (changed.has(pv) ? state : (baseline.pages[tab]?.[pv] ?? alarm)) &&
        tolerated[pv] !== alarm
    );
    if (Object.keys(now).some((pv) => changed.has(pv))) touched.add(tab);
    const shownTolerated = Object.entries(now).filter(([pv, alarm]) => tolerated[pv] === alarm && baseline.pages[tab]?.[pv] !== alarm);
    if (shownTolerated.length) showsTolerated.set(tab, shownTolerated.map(([, alarm]) => alarm));
    check(
      wrong.length === 0,
      `${label}, ${tab}: ${Object.keys(now).length} PVs, the affected ones ${state}, the others as before${
        wrong.length ? ` (wrong: ${wrong.map(([pv, a]) => `${pv}=${a}`).join(", ")})` : ""
      }`
    );
    checkWords(els, `${label}, ${tab}`);
    await extra(page, tab);
    await page.close();
  }
  // The dots, in a main window of their own: each dot is the worst of every
  // PV of its page, hidden pages included, so it settles once all of them
  // have reported (later with an IOC down: pvServer waits for its PVs).
  // A tolerated state counts on the tabs that showed it, and on
  // Infrastructure, whose dot is the worst of every record: their dot may be
  // that state too.
  const rank = ["ok", "minor", "major", "invalid", "disconnected"];
  const worse = (a, b) => (rank.indexOf(b) > rank.indexOf(a) ? b : a);
  const seen = [...showsTolerated.values()].flat();
  if (seen.length) showsTolerated.set("infrastructure", [...(showsTolerated.get("infrastructure") ?? []), ...seen]);
  const want = Object.fromEntries(
    Object.keys(baseline.tabs).map((tab) => [
      tab,
      touched.has(tab)
        ? [state]
        : [baseline.tabs[tab], ...(showsTolerated.get(tab) ?? []).map((alarm) => worse(baseline.tabs[tab], alarm))],
    ])
  );
  const page = await openMain("overview");
  let dots = {};
  let waited = 0;
  for (; waited < 30; waited += 1) {
    dots = await tabStates(page);
    if (Object.keys(want).every((tab) => want[tab].includes(dots[tab]))) break;
    await page.waitForTimeout(1000);
  }
  await page.close();
  // How long an operator who opens a window in this state sees other dots.
  console.log(`note: ${label}: tab dots as expected after ${waited} s`);
  for (const tab of Object.keys(want)) {
    check(want[tab].includes(dots[tab]), `${label}: tab ${tab} shows ${dots[tab]}, expected ${[...new Set(want[tab])].join(" or ")}`);
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
      if (await page.locator("svg[data-page]").count()) {
        const overlaps = await tagOverlaps(page);
        check(overlaps.length === 0, `${tab}: no two tags overlap at 1920 x 1080${overlaps.length ? ` (${overlaps.join(", ")})` : ""}`);
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
      await pageShot(page, `normal-${tab}`, tab !== "overview");
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
      if (["overview", "plasma-generator", "extraction"].includes(tab)) await pageShot(page, `fault-${tab}`, tab !== "overview");
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
    // After an IOC start (args: a Channel Access read of the moment, then the
    // records still expected unprocessed): those of them that Channel Access
    // reads INVALID with status UDF may show INVALID. The note names every
    // record that is INVALID/UDF at that moment.
    const [read, ...expectedUdf] = args;
    const reads = read ? JSON.parse(fs.readFileSync(`${work}/${read}`, "utf8")) : {};
    const udf = Object.keys(reads).filter((pv) => reads[pv].severity === 3 && reads[pv].status === 17);
    if (udf.length) console.log(`note: INVALID (UDF) through Channel Access, not processed since the IOC start: ${udf.join(", ")}`);
    const tolerated = Object.fromEntries(udf.filter((pv) => expectedUdf.includes(pv)).map((pv) => [pv, "invalid"]));
    await comparePages("after clearing", new Set(), "ok", undefined, { ...loggerTolerance(), ...tolerated });
  },

  async iocdown() {
    const [ioc] = args;
    const changed = new Set([
      ...Object.values(registry.iocs[ioc].roles),
      ...installed.filter((id) => devices[id].ioc === ioc).flatMap(expected),
    ]);
    await comparePages(`${ioc} stopped`, changed, "disconnected", async (page, tab) => {
      if (tab === "overview") {
        const banner = await page.locator("[data-banner]").innerText();
        check(banner.includes("mode unknown"), `banner with the IOC stopped: ${banner}`);
        const chip = await page.locator(`div[data-ioc="${ioc}"]`).getAttribute("data-alarm");
        check(chip === "disconnected", `IOC chip of ${ioc}: ${chip}`);
        await shot(page, "iocdown-overview", false);
      }
      if (tab === "plasma-generator") await pageShot(page, "iocdown-plasma-generator");
    }, loggerTolerance());
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
      await page.waitForTimeout(800); // the dialog fades in
      await shot(page, `write-confirm-${id}-${channel}`, false);
      await page.getByRole("dialog").getByRole("button").last().click();
    }
    await page.waitForTimeout(1000);
    await page.close();
  },

  async shows() {
    const [id, role, value] = args;
    const page = await openDevice(id);
    await settle(page);
    const word = devices[id].pvs[devices[id].roles[role]].states[Number(value)];
    const group = page.locator(`[data-part="Controls"] [data-pv="${devices[id].roles[role]}"]`);
    const pressed = await group.locator('[aria-pressed="true"]').innerText();
    check(pressed === word, `${id} ${role}: the switch shows ${pressed}, expected ${word}`);
    await shot(page, `latch-${id}-request-${word.toLowerCase()}`, false);
    await page.close();
  },

  async tagsetpoint() {
    const [tab, id, role, how] = args;
    const pv = devices[id].roles[role];
    const page = await openMain(tab);
    await settle(page);
    const input = tagOf(page, tab, id).locator(`input[data-pv="${pv}"]`);
    const shown = await input.inputValue();
    if (how === "escape") {
      const value = testValue(id, role, 0.3);
      await input.click();
      await input.fill(String(value));
      check((await input.getAttribute("data-unsent")) === "true", `${tab}, tag ${id} ${role}: a typed ${value} is marked unsent`);
      await input.press("ArrowUp");
      await page.mouse.wheel(0, -300);
      check((await input.inputValue()) === String(value), `${tab}, tag ${id} ${role}: the arrow keys and the mouse wheel leave the entry as it is`);
      await shot(page, `inplace-unsent-${id}`, false);
      await input.press("Escape");
      await page.waitForTimeout(300);
      const after = await input.inputValue();
      check(
        after === shown && (await input.getAttribute("data-unsent")) === null,
        `${tab}, tag ${id} ${role}: Escape gives the entry up, the field shows the IOC's ${after} again (before: ${shown})`
      );
      await page.close();
      return;
    }
    const value = testValue(id, role, 0.2);
    const before = context.pages().length;
    await input.click();
    await input.fill(String(value));
    await input.press("Enter");
    await page.waitForTimeout(1000);
    check(context.pages().length === before, `${tab}, tag ${id} ${role}: typing in the tag opens no device window`);
    await shot(page, `inplace-setpoint-${id}`, false);
    await page.close();
    fs.writeFileSync(`${work}/setpoint.txt`, `${devices[id].pvs[pv].readback ?? pv} ${value}\n`);
    pass(`typed ${value} into the ${tab} tag of ${id} ${role} and pressed Enter`);
  },

  async tagcommand() {
    const [tab, id, channel, role, value, dialog] = args;
    const page = await openMain(tab);
    await settle(page);
    const before = context.pages().length;
    const group = tagOf(page, tab, id, channel).locator(`[data-pv="${rolesOf(id, channel)[role]}"]`);
    await group.getByRole("button").nth(Number(value)).click();
    const shown = await page
      .getByRole("dialog")
      .waitFor({ state: "visible", timeout: 2000 })
      .then(() => true)
      .catch(() => false);
    check(shown === (dialog === "dialog"), `${tab}, tag ${id} ${channel} ${role} := ${value}: ${shown ? "asks" : "does not ask"} for confirmation`);
    if (shown) {
      await page.waitForTimeout(800); // the dialog fades in
      await shot(page, `inplace-confirm-${id}-${channel}`, false);
      await page.getByRole("dialog").getByRole("button").last().click();
    }
    await page.waitForTimeout(1000);
    check(context.pages().length === before, `${tab}, tag ${id} ${channel} ${role}: the switch in the tag opens no device window`);
    await page.close();
  },

  async loop() {
    const [id, what] = args;
    const roles = devices[id].roles;
    const words = (role) => devices[id].pvs[roles[role]].states;
    const switchIn = (where) => where.locator(`[data-pv="${roles.mode_cmd}"]`);
    const pressed = (where) => switchIn(where).locator('[aria-pressed="true"]').innerText();
    const field = (where, role) => where.locator(`input[data-pv="${roles[role]}"]`).inputValue();
    const tagValue = (tag, role) => tag.locator(`[data-pv="${roles[role]}"] [data-value]`).textContent();
    const [manual, pid] = words("mode_cmd");
    if (what === "refuse") {
      const page = await openDevice(id);
      await settle(page);
      const controls = page.locator('[data-part="Controls"]');
      const permits = [];
      for (const role of ["permit1", "permit2", "permit3"]) permits.push(await field(controls, role));
      const expected = permits.find((word) => word !== words("permit1")[0]);
      check(expected !== undefined, `${id}: a permit is not fulfilled (${permits.join(", ")})`);
      await switchIn(controls).getByRole("button", { name: pid }).click();
      const [[request, reason], seconds] = await until(
        async () => [await pressed(controls), await field(controls, "reason")],
        ([r, why]) => r === manual && why === expected,
        3
      );
      check(request === manual && reason === expected, `${id}: PID refused, the request back at ${request} and the reason "${reason}" (expected "${expected}") after ${seconds} s`);
      const box = await controls.locator(`input[data-pv="${roles.reason}"]`).boundingBox();
      const switchBox = await switchIn(controls).boundingBox();
      check(box && box.y + box.height <= 760 && box.y - switchBox.y < 120, `${id}: the reason stands right below the switch, in sight without scrolling`);
      await shot(page, `loop-device-refused`, false);
      await page.close();
      const main = await openMain(slug(devices[id].page));
      await settle(main);
      const tagReason = await tagValue(tagOf(main, slug(devices[id].page), id), "reason");
      check(tagReason === expected, `${id}: the tag on ${devices[id].page} shows the reason "${tagReason}"`);
      await main.close();
      return;
    }
    const main = await openMain(slug(devices[id].page));
    await settle(main);
    const tag = tagOf(main, slug(devices[id].page), id);
    const before = context.pages().length;
    await switchIn(tag).getByRole("button", { name: pid }).click();
    const [mode, seconds] = await until(() => tagValue(tag, "mode"), (m) => m === pid, 5);
    check(mode === pid, `${id}: PID switched in its tag, the tag shows mode ${mode} after ${seconds} s`);
    check(context.pages().length === before, `${id}: the switch in the tag opens no device window`);
    await pageShot(main, "loop-plasma-generator-pid");
    const page = await openDevice(id);
    await settle(page);
    const controls = page.locator('[data-part="Controls"]');
    const lamp = () => controls.locator(`[data-pv="${roles.mode}"] [data-value]`).textContent();
    const [windowMode] = await until(lamp, (m) => m === pid, 5);
    check(windowMode === pid, `${id}: the device window shows mode ${windowMode}`);
    const value = testValue(id, "sp_cmd", 0.2);
    const input = controls.locator(`input[data-pv="${roles.sp_cmd}"]`);
    await input.fill(String(value));
    await input.press("Enter");
    await page.waitForTimeout(1500);
    await shot(page, "loop-device-pid", false);
    await page.getByRole("tab", { name: "Trend" }).click();
    await page.waitForTimeout(4000);
    await shot(page, "loop-device-pid-trend", false);
    await page.getByRole("tab", { name: "Controls" }).click();
    await switchIn(controls).getByRole("button", { name: manual }).click();
    const [back] = await until(lamp, (m) => m === manual, 5);
    check(back === manual, `${id}: MANUAL from the device window, it shows mode ${back}`);
    await page.close();
    const [tagBack] = await until(() => tagValue(tag, "mode"), (m) => m === manual, 5);
    check(tagBack === manual, `${id}: the tag shows mode ${tagBack} again`);
    await pageShot(main, "loop-plasma-generator-manual");
    await main.close();
    fs.writeFileSync(`${work}/setpoint.txt`, `${roles.sp_cmd} ${value}\n`);
    pass(`typed ${value} into the set point of ${id} in PID`);
  },

  async logger() {
    const want = Number(args[0]) === 1 ? "ok" : "major";
    const word = Number(args[0]) === 1 ? "alive" : "dead";
    for (const id of services) {
      const chipState = async (page) => {
        const chip = page.locator(`[data-service="${id}"]`);
        const [state] = await until(() => chip.getAttribute("data-alarm"), (s) => s === want, 10);
        return [state, await chip.innerText()];
      };
      const main = await openMain("infrastructure");
      await settle(main);
      const [state, text] = await chipState(main);
      check(state === want, `${id} ${word}: its chip in the main window's strip is ${state} ("${text}"), expected ${want}`);
      check(
        (await main.locator(`svg[data-page] g[data-device="${id}"]`).count()) === 0,
        `${id}: on no drawing and in no list area of the main window's pages`
      );
      const card = main.locator(`[data-service-card="${id}"]`);
      const shown = await card.locator("[data-pv]").evaluateAll((els) => els.map((el) => el.dataset.pv));
      const missing = expected(id).filter((pv) => !shown.includes(pv));
      check(
        (await card.isVisible()) && missing.length === 0,
        `${id}: its widget on the Infrastructure page shows all ${expected(id).length} records${missing.length ? ` (missing: ${missing.join(", ")})` : ""}`
      );
      const alive = await card.locator(`[data-pv="${devices[id].roles.alive}"]`).getAttribute("data-alarm");
      check(alive === want, `${id} ${word}: its widget shows alive ${alive}`);
      await pageShot(main, `logger-${word}-infrastructure`);
      await main.close();
      const win = await open("/page/diagnostics");
      await settle(win);
      const [winState] = await chipState(win);
      check(winState === want, `${id} ${word}: its chip in a page window is ${winState}`);
      await shot(win, `logger-${word}-page-window`, false);
      await win.close();
      const device = await openDevice(id);
      await settle(device);
      const [deviceState] = await chipState(device);
      check(deviceState === want, `${id} ${word}: its chip in its device window is ${deviceState}`);
      await shot(device, `logger-${word}-device`, false);
      await device.close();
    }
  },

  async windows() {
    const [tab] = args;
    const main = await openMain("overview");
    await settle(main);
    const label = (slug) => main.locator(`[data-tab="${slug}"]`);
    const popOut = async (slug) => {
      const [win] = await Promise.all([context.waitForEvent("page"), label(slug).locator("[data-popout]").click()]);
      await win.waitForSelector("[data-banner]");
      return win;
    };
    const isOut = (slug) => label(slug).getAttribute("data-out").then((out) => out === "true");
    const shownHere = (slug) => main.locator(`[data-page-tab="${slug}"] svg[data-page], [data-page-tab="${slug}"] table`).first().isVisible();

    // Out: an ordinary route, complete in itself, with the values Channel Access reads.
    const dots = await tabStates(main);
    const baselineTab = (slug) => dots[slug];
    const win = await popOut(tab);
    check(new URL(win.url()).pathname === `/page/${tab}`, `${tab} opens in a window of its own at ${new URL(win.url()).pathname}`);
    const els = await settle(win);
    check(els.length > 0 && els.every((el) => el.alarm !== "disconnected"), `${tab} window: ${els.length} PVs, all connected`);
    checkWords(els, `${tab} window`);
    const title = await win.title();
    const name = await win.locator("[data-page-name]").innerText();
    check(slug(name) === tab && title === `[SIM] ${name}`, `${tab} window: its page name "${name}", window title "${title}"`);
    check((await win.locator("[data-banner]").innerText()).startsWith("EMULATOR"), `${tab} window: emulator banner`);
    const own = await win.locator("[data-page-name] + [data-alarm]").getAttribute("data-alarm");
    check(own === baselineTab(tab), `${tab} window: its own severity ${own}, as its tab in the main window`);
    fs.writeFileSync(`${work}/window.json`, JSON.stringify({ expert: shownValues(els) }, null, 1));

    // Marked in the main window, its dot kept; a click brings the window to the front.
    const [marked] = await until(() => isOut(tab), (out) => out, 3);
    check(marked && (await label(tab).locator("[data-alarm]").count()) === 1, `${tab}: its tab is marked as out and keeps its dot`);
    await win.evaluate(() => {
      window.mist2Front = 0;
      window.focus = () => {
        window.mist2Front += 1;
      };
    });
    await label(tab).click();
    await main.waitForTimeout(500);
    check((await win.evaluate(() => window.mist2Front)) > 0, `${tab}: a click on its tab brings its window to the front`);
    check(new URL(main.url()).searchParams.get("tab") !== tab, `${tab}: the main window stays on the page it showed`);
    await win.waitForTimeout(3000);
    const pictures = await Promise.all([main, win].map((p) => p.screenshot()));
    const board = await context.newPage();
    await board.setViewportSize({ width: 1920, height: 560 });
    await board.setContent(
      `<body style="margin:0;background:#111;display:flex;gap:8px">${pictures
        .map((png) => `<img style="width:956px" src="data:image/png;base64,${png.toString("base64")}">`)
        .join("")}</body>`
    );
    await board.screenshot({ path: `${shots}/windows-page-beside-main.png` });
    await board.close();

    // A device opened from the page window: the same one window as from the main window.
    const device = await win.locator(`[data-page-tab="${tab}"] svg[data-page] g[data-device]`).first().getAttribute("data-device");
    const [deviceWindow] = await Promise.all([
      context.waitForEvent("page"),
      win.locator(`[data-page-tab="${tab}"] g[data-device="${device}"]`).first().click({ position: { x: 20, y: 8 } }),
    ]);
    await deviceWindow.waitForLoadState();
    const count = context.pages().length;
    await main.locator(`[data-page-tab="overview"] g[data-device="${device}"]`).first().click({ position: { x: 20, y: 8 } });
    await main.waitForTimeout(1500);
    check(context.pages().length === count, `${device} opened from the ${tab} window, then from the main window: one window`);

    // Attach, and the browser's own close: the page is back in the main window.
    await Promise.all([win.waitForEvent("close"), win.locator("[data-attach]").click()]);
    const [back] = await until(async () => !(await isOut(tab)) && (await shownHere(tab)), (ok) => ok, 3);
    check(back, `${tab}: "attach" closes its window and the main window shows the page again`);
    check(!deviceWindow.isClosed(), `the device window stays open when the page goes back`);
    await shot(main, `windows-attached-${tab}`, false);
    const again = await popOut(tab);
    await again.close();
    const [backAgain] = await until(async () => !(await isOut(tab)) && (await shownHere(tab)), (ok) => ok, 3);
    check(backAgain, `${tab}: closing its window by the browser brings the page back too`);

    // Every page out: the main window keeps its frame.
    const out = [];
    for (const slug of tabs) out.push(await popOut(slug));
    await main.waitForTimeout(1500);
    const allMarked = (await Promise.all(tabs.map(isOut))).every(Boolean);
    check(
      allMarked &&
        (await main.locator("header button", { hasText: "ALL HV OFF" }).isVisible()) &&
        (await main.locator("[data-banner]").isVisible()) &&
        (await main.locator('[role="tab"]').count()) === tabs.length,
      `every page out: the main window still shows the ${tabs.length} tabs, all marked, the status strip and ALL HV OFF`
    );
    await shot(main, "windows-all-out", false);

    // A reload of the main window closes every window it opened.
    await main.reload();
    await main.waitForTimeout(1500);
    check([...out, deviceWindow].every((p) => p.isClosed()), "a reload of the main window closes the page and device windows");
    check(!(await isOut(tab)), "after the reload every page is in the main window");
    await main.close();
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
