import React, { createContext, useContext, useMemo, useSyncExternalStore } from "react";
import EpicsPV from "React-Automation-Studio/components/SystemComponents/EpicsPV";
import { alarmState, worst } from "./severity";

// Holds the alarm state of a set of PVs, each subscribed once, and tells the
// components that show a worst state (tabs, tags, symbols, device windows)
// only when one of these states changes, not on every value. The reports
// come from the effects of the RAS EpicsPV components, so the readers are told
// from a timer, outside React's effect phase (an update set there counts
// toward React's limit of nested effect updates), and at most every 100 ms,
// since hundreds of PVs connect at once when a window opens.
const tellAfter = 100;

const createStore = () => {
  const states = new Map();
  const listeners = new Set();
  const reporters = new Map();
  let timer = null;
  const tell = () => {
    timer ??= setTimeout(() => {
      timer = null;
      listeners.forEach((listener) => listener());
    }, tellAfter);
  };
  return {
    reporter: (name) => {
      if (!reporters.has(name)) {
        reporters.set(name, (pv) => {
          const state = alarmState(pv.initialized, pv.severity);
          if (states.get(name) !== state) {
            states.set(name, state);
            tell();
          }
        });
      }
      return reporters.get(name);
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    worst: (names) => worst(names.map((name) => states.get(name) ?? "disconnected")),
  };
};

const AlarmContext = createContext(null);

export const AlarmProvider = ({ pvs, children }) => {
  const store = useMemo(createStore, []);
  return (
    <AlarmContext.Provider value={store}>
      {pvs.map((name) => (
        <EpicsPV key={name} pv={name} pvData={store.reporter(name)} />
      ))}
      {children}
    </AlarmContext.Provider>
  );
};

// The worst alarm state of some PVs of the provider; "ok" for none.
export const useWorstAlarm = (names) => {
  const store = useContext(AlarmContext);
  return useSyncExternalStore(store.subscribe, () => store.worst(names));
};
