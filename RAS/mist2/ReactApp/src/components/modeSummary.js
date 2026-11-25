// What the window title and the banner say about the IOCs' modes (LAYOUT.md
// 1.3; open point P68). `entries` is [[IOC name, mode], ...] with the mode as
// the IOC reports it ("sim", "real") or null while it is not connected.
//
//   an IOC reports sim, none reports real    title "[SIM] ", banner EMULATOR
//   IOCs report both                         title "[MIXED] ", banner MIXED
//   every IOC reports real                   no prefix, no banner
//   real, others not known                   no prefix, a neutral banner naming them
//   no IOC reports a mode                    no prefix, a neutral banner
//
// An IOC whose mode is not known (not connected, or a word other than sim or
// real) is named as such and never makes the system an emulator.
export const modeSummary = (entries) => {
  const known = (mode) => mode === "sim" || mode === "real";
  const sim = entries.some(([, mode]) => mode === "sim");
  const real = entries.some(([, mode]) => mode === "real");
  const unknown = entries.filter(([, mode]) => !known(mode));
  const part = ([name, mode]) =>
    mode === "sim" ? `${name} in mode sim` : mode === "real" ? `${name} on real hardware` : `${name}: mode unknown`;
  if (sim && !real) {
    const text =
      unknown.length === 0
        ? `EMULATOR — ${entries.map(([name]) => name).join(" and ")} report mode sim. No hardware is connected.`
        : `EMULATOR — ${entries.map(part).join(", ")}.`;
    return { prefix: "[SIM] ", banner: text, kind: "emulator" };
  }
  if (sim && real) return { prefix: "[MIXED] ", banner: `MIXED — ${entries.map(part).join(", ")}.`, kind: "mixed" };
  if (unknown.length === 0) return { prefix: "", banner: null, kind: "real" };
  const lead = real ? "MODE NOT KNOWN" : "NO IOC REPORTS ITS MODE";
  return { prefix: "", banner: `${lead} — ${entries.map(part).join(", ")}.`, kind: "unknown" };
};

export default modeSummary;
