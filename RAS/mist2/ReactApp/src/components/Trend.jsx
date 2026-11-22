import React, { useEffect, useRef, useState } from "react";
import Plot from "react-plotly.js";
import { useTheme } from "@mui/material/styles";
import { useEpicsPV } from "React-Automation-Studio/components/SystemComponents/EpicsPV";
import { alarmState } from "../alarm/severity";

const keep = 3000; // points per line
const redrawEvery = 1000; // ms

// One line: every monitor update of the PV is appended to its series, which
// lives in a ref, so no state is set. A value is a point at the record's time
// stamp. An INVALID record and a lost connection end the line there (the
// value holds until then), and the next valid value starts it again.
const Series = ({ pv, series }) => {
  const { initialized, value, severity, timestamp } = useEpicsPV({ pv });
  useEffect(() => {
    const line = (series.current[pv] ??= { x: [], y: [] });
    const state = alarmState(initialized, severity);
    const valid = state !== "disconnected" && state !== "invalid";
    const last = line.x.length - 1;
    const drawing = last >= 0 && line.y[last] !== null;
    if (!valid && !drawing) return;
    // Never before the point before. A line starts when its value arrives:
    // the time stamp of a record that is not processed can be days old.
    const stamp = state === "disconnected" ? Date.now() : Number(timestamp) * 1000;
    const time = new Date(Math.max(stamp, drawing ? line.x[last].getTime() : Date.now()));
    if (valid) {
      line.x.push(time);
      line.y.push(Number(value));
    } else {
      line.x.push(time, time);
      line.y.push(line.y[last], null);
    }
    while (line.x.length > keep) {
      line.x.shift();
      line.y.shift();
    }
  }, [initialized, value, severity, timestamp, pv, series]);
  return null;
};

// A time-stamped trend of some PVs on monitors, redrawn once a second while it
// is visible. It replaces RAS GraphY, whose display loop sets state in an
// effect every 100 ms (GraphY.tsx, PlotData: setTimeout -> setTrigger ->
// effect -> setDelayedData): with a dozen graphs mounted, React's count of
// nested effect updates never returns to zero and reaches its limit. Here the
// redraw is set from a timer, outside the effect phase. The history grows
// while the page is hidden, as with the mounted pages of the 2023 GUI.
//
// A monitor sends a value when it changes, and the value holds until the next
// one: the lines are steps, and each runs on to the present (the browser's
// clock; the points carry the IOC's). A zoom by the operator stays until a
// double click.
const Trend = ({ pvs, legend, log, height }) => {
  const theme = useTheme();
  const series = useRef({});
  const box = useRef(null);
  const opened = useRef(Date.now());
  const [drawn, setDrawn] = useState(opened.current);
  useEffect(() => {
    const timer = setInterval(() => {
      if (box.current?.offsetParent) setDrawn(Date.now());
    }, redrawEvery);
    return () => clearInterval(timer);
  }, []);
  const lines = pvs.map((pv, index) => {
    const { x = [], y = [] } = series.current[pv] ?? {};
    const last = x.length - 1;
    const holds = last >= 0 && y[last] !== null && drawn > x[last].getTime();
    return {
      x: holds ? [...x, new Date(drawn)] : x,
      y: holds ? [...y, y[last]] : y,
      name: legend[index],
      type: "scatter",
      mode: "lines",
      line: { shape: "hv" },
    };
  });
  // Without a value Plotly draws axes of its own invention. Leave them out, and say what an
  // empty graph means once the values have had time to arrive.
  const empty = lines.every((line) => !line.x.length);
  const told = empty && drawn - opened.current > 3 * redrawEvery;
  const axis = {
    gridcolor: theme.palette.divider,
    linecolor: theme.palette.text.secondary,
    zeroline: false,
    automargin: true,
    showticklabels: !empty,
  };
  return (
    <div ref={box} style={{ width: "100%", height }}>
      {pvs.map((pv) => (
        <Series key={pv} pv={pv} series={series} />
      ))}
      <Plot
        data={lines}
        layout={{
          datarevision: drawn,
          uirevision: true,
          autosize: true,
          margin: { t: 8, r: 8, b: 32, l: 8 },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          font: { color: theme.palette.text.secondary, size: 11 },
          xaxis: { ...axis, type: "date" },
          yaxis: { ...axis, type: log ? "log" : "linear", tickformat: log ? ".1e" : undefined },
          annotations: told
            ? [{ text: "no valid value yet", showarrow: false, xref: "paper", yref: "paper", x: 0.5, y: 0.5 }]
            : [],
          showlegend: true,
          legend: { orientation: "h", x: 1, xanchor: "right", y: 1, yanchor: "bottom", bgcolor: "rgba(0,0,0,0)" },
        }}
        config={{ displaylogo: false }}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
};

export default Trend;
