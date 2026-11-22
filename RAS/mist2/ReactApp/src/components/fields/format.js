import { isText } from "../../registry";

// Widget props of a read-back: with words (from the registry) the value is
// the state index shown by its word; a text record by its string; a number
// raw, formatted by valueText.
export const readProps = (pv, words) =>
  words ? { custom_selection_strings: words, usePvUnits: true } : { useStringValue: isText(pv), usePvUnits: true };

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

// The text of a value from the props a Widget passes to its component: the
// state word, the text, or the number in the record's precision, in exponent
// format or with an SI prefix where the unit and the value call for it.
// pvServer may send a number as a string, so a value that is not a text
// record and reads as a finite number is a number.
export const valueText = ({ value, enumStrs, units, pvData, useStringValue }) => {
  if (enumStrs?.length) return enumStrs[Number(value)] ?? String(value);
  const number = Number(pvData.value);
  const parts =
    !useStringValue && pvData.value !== "" && Number.isFinite(number)
      ? formatNumber(number, pvData.metadata.precision, units)
      : [value, units];
  return parts.filter((part) => part !== "" && part != null).join(" ");
};
