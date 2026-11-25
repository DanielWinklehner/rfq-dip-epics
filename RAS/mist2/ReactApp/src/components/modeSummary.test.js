// The title and banner for every combination of IOC modes (P68, T31 D7).
//   docker run --rm -v "$PWD/RAS/mist2/ReactApp/src:/t/src:ro" -w /t mist2ras-node-cache \
//     sh -c 'ln -s /ReactApp/node_modules node_modules && npx vitest run --config /dev/null src/components/modeSummary.test.js'
import { describe, expect, test } from "vitest";
import modeSummary from "./modeSummary";

const R = "Rack IOC";
const H = "HV platform IOC";

describe("modeSummary", () => {
  test("both IOCs in the emulation: [SIM] and EMULATOR", () => {
    const m = modeSummary([[R, "sim"], [H, "sim"]]);
    expect(m.prefix).toBe("[SIM] ");
    expect(m.banner).toBe("EMULATOR — Rack IOC and HV platform IOC report mode sim. No hardware is connected.");
  });
  test("one in the emulation, the other not connected: [SIM], EMULATOR naming the unknown one", () => {
    const m = modeSummary([[R, "sim"], [H, null]]);
    expect(m.prefix).toBe("[SIM] ");
    expect(m.banner).toBe("EMULATOR — Rack IOC in mode sim, HV platform IOC: mode unknown.");
  });
  test("every IOC on real hardware: no [SIM], no banner", () => {
    expect(modeSummary([[R, "real"], [H, "real"]])).toEqual({ prefix: "", banner: null, kind: "real" });
  });
  test("real and not connected (the lab on 2026-11-25): no [SIM], no emulator banner", () => {
    const m = modeSummary([[R, "real"], [H, null]]);
    expect(m.prefix).toBe("");
    expect(m.kind).toBe("unknown");
    expect(m.banner).not.toMatch(/EMULATOR|MIXED/);
    expect(m.banner).toContain("HV platform IOC: mode unknown");
    expect(m.banner).toContain("Rack IOC on real hardware");
  });
  test("no IOC connected: no [SIM], a neutral banner", () => {
    const m = modeSummary([[R, null], [H, undefined]]);
    expect(m.prefix).toBe("");
    expect(m.kind).toBe("unknown");
    expect(m.banner).not.toMatch(/EMULATOR|MIXED/);
    expect(m.banner).toContain("Rack IOC: mode unknown, HV platform IOC: mode unknown");
  });
  test("a mix: the mixed banner and a title that is not [SIM]", () => {
    const m = modeSummary([[R, "real"], [H, "sim"]]);
    expect(m.prefix).toBe("[MIXED] ");
    expect(m.banner).toBe("MIXED — Rack IOC on real hardware, HV platform IOC in mode sim.");
  });
  test("a mode word that is neither sim nor real is unknown", () => {
    const m = modeSummary([[R, "test"], [H, "real"]]);
    expect(m.prefix).toBe("");
    expect(m.banner).toContain("Rack IOC: mode unknown");
  });
});
