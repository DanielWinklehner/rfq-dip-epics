import Command from "./Command";
import Controller from "./Controller";
import Gauge from "./Gauge";
import Interlock from "./Interlock";
import Mfc from "./Mfc";
import Reading from "./Reading";
import Supply from "./Supply";
import Turbo from "./Turbo";
import Valve from "./Valve";

// The widget of each registry class (LAYOUT.md 1.4). Each takes a device id.
const widgets = {
  supply: Supply,
  valve: Valve,
  gauge: Gauge,
  turbo: Turbo,
  mfc: Mfc,
  reading: Reading,
  interlock: Interlock,
  command: Command,
};

export const widgetOf = (deviceClass) => widgets[deviceClass] ?? Controller;
