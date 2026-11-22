import React, { useEffect, useRef, useState } from "react";
import Plot from "react-plotly.js";
import { useTheme } from "@mui/material/styles";
import { useEpicsPV } from "React-Automation-Studio/components/SystemComponents/EpicsPV";

const keep = 3000; // points per line
const redrawEvery = 1000; // ms

// One line: every monitor update of the PV is appended to its series, which
// lives in a ref, so no state is set.
const Series = ({ pv, series }) => {
  const { initialized, value, timestamp } = useEpicsPV({ pv });
  useEffect(() => {
    if (!initialized) return;
    const line = (series.current[pv] ??= { x: [], y: [] });
    line.x.push(new Date(Number(timestamp) * 1000));
    line.y.push(Number(value));
    if (line.x.length > keep) {
      line.x.shift();
      line.y.shift();
    }
  }, [initialized, value, timestamp, pv, series]);
  return null;
};

// A time-stamped trend of some PVs on monitors, redrawn once a second while it
// is visible. It replaces RAS GraphY, whose display loop sets state in an
// effect every 100 ms (GraphY.tsx, PlotData: setTimeout -> setTrigger ->
// effect -> setDelayedData): with a dozen graphs mounted, React's count of
// nested effect updates never returns to zero and reaches its limit. Here the
// redraw is set from a timer, outside the effect phase. The history grows
// while the page is hidden, as with the mounted pages of the 2023 GUI.
const Trend = ({ pvs, legend, log, height }) => {
  const theme = useTheme();
  const series = useRef({});
  const box = useRef(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      if (box.current?.offsetParent) setRevision((r) => r + 1);
    }, redrawEvery);
    return () => clearInterval(timer);
  }, []);
  const axis = {
    gridcolor: theme.palette.divider,
    linecolor: theme.palette.text.secondary,
    zeroline: false,
    automargin: true,
  };
  return (
    <div ref={box} style={{ width: "100%", height }}>
      {pvs.map((pv) => (
        <Series key={pv} pv={pv} series={series} />
      ))}
      <Plot
        data={pvs.map((pv, index) => ({
          x: series.current[pv]?.x ?? [],
          y: series.current[pv]?.y ?? [],
          name: legend[index],
          type: "scatter",
          // Markers too: a value that does not change sends one update only.
          mode: "lines+markers",
          marker: { size: 3 },
        }))}
        layout={{
          datarevision: revision,
          autosize: true,
          margin: { t: 8, r: 8, b: 32, l: 8 },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          font: { color: theme.palette.text.secondary, size: 11 },
          xaxis: { ...axis, type: "date" },
          yaxis: { ...axis, type: log ? "log" : "linear", tickformat: log ? ".1e" : undefined },
          showlegend: true,
          legend: { orientation: "h", x: 1, xanchor: "right", y: 1, bgcolor: "rgba(0,0,0,0)" },
        }}
        config={{ displaylogo: false }}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
};

export default Trend;
