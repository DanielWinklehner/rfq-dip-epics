// Units whose values span decades: always in exponent format, trends on a log scale.
const decadeUnits = ["torr", "mbar", "pa"];
export const spansDecades = (units) => decadeUnits.includes((units ?? "").toLowerCase());

// SI units that take a prefix when a value is far from 1 (1.00 µA, 20.0 kV).
const siUnits = ["A", "V", "W", "Hz", "s"];
const prefixes = { "-12": "p", "-9": "n", "-6": "µ", "-3": "m", 3: "k", 6: "M" };

const formatNumber = (value, prec, units) => {
  const magnitude = Math.abs(value);
  if (spansDecades(units)) return [value.toExponential(2), units];
  if (siUnits.includes(units) && magnitude > 0 && (magnitude < 1e-2 || magnitude >= 1e4)) {
    const exponent = Math.min(6, Math.max(-12, Math.floor(Math.log10(magnitude) / 3) * 3));
    // Keep the record's resolution, up to three decimals: 15234 V with precision 0 reads
    // 15.234 kV, not 15.2 kV.
    const scaled = value / 10 ** exponent;
    const decimals = Math.min(3, Math.max(0, prec + exponent));
    const text = Number.isInteger(prec) ? scaled.toFixed(decimals) : scaled.toPrecision(3);
    return [text, `${prefixes[exponent]}${units}`];
  }
  return [Number.isInteger(prec) ? value.toFixed(prec) : String(value), units];
};

// The text of a value of the RAS socket hook (useEpicsPV): the state word
// (the registry's `words`, else the record's), the text of a text record, or
// the number in the record's precision, in exponent format or with an SI
// prefix where the unit and the value call for it. pvServer may send a number
// as a string, so a value that is not text and reads as a number is a number.
export const valueText = (pv, words, text) => {
  const strings = words ?? pv.metadata.enum_strs;
  if (strings?.length) return strings[Number(pv.value)] ?? String(pv.value);
  const { units, precision } = pv.metadata;
  const number = Number(pv.value);
  const parts =
    !text && pv.value !== "" && Number.isFinite(number)
      ? formatNumber(number, precision, units)
      : [pv.value, units];
  return parts.filter((part) => part !== "" && part != null).join(" ");
};
