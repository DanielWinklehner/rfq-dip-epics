// The word for the value of a binary or multi-bit record: its state string,
// or "off"/"on" for a record that has none (the valve box channels).
const stateText = (value, enumStrs) =>
  enumStrs?.[Number(value)] || (Number(value) ? "on" : "off");

export default stateText;
