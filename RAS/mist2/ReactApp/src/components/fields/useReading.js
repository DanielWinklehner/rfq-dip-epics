import { useEpicsPV } from "React-Automation-Studio/components/SystemComponents/EpicsPV";
import { useContextMenu } from "React-Automation-Studio/components/SystemComponents/Utils/widgetHooks";
import { alarmState, displayText } from "../../alarm/severity";
import { isText } from "../../registry";
import { valueText } from "./format";

// A read-back for display: the RAS socket hook sets the PV's state in the
// socket handler, and nothing here sets state in an effect. (The RAS Widget
// and PV components pass every update on through three effects that each set
// state; with a few hundred of them mounted, React's count of nested
// passive-effect updates never returns to zero and reaches its limit.)
// `words` are the registry's words for the values; `field` reads another
// field of the record (VAL$ for the full text of a long string).
const useReading = (name, words, field) => {
  const text = !words && isText(name);
  const pv = useEpicsPV({ pv: field ? `${name}.${field}` : name, useStringValue: text });
  const state = alarmState(pv.initialized, pv.severity);
  const [menu, openMenu] = useContextMenu([{ PVs: [pv] }], true);
  return { state, text: displayText(state, valueText(pv, words, text)), on: Number(pv.value) !== 0, menu, openMenu };
};

export default useReading;
