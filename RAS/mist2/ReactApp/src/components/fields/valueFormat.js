import { isText } from "../../registry";

// Widget props that show a read-back as its record says: text records by
// their string, numbers with the record's unit and precision, or in exponent
// format.
const valueFormat = (pv, exponent) => {
  const text = isText(pv);
  return {
    useStringValue: text,
    usePvUnits: true,
    usePvPrecision: !text && !exponent,
    numberFormat: exponent ? { notation: "exponential", precision: 3 } : undefined,
  };
};

export default valueFormat;
