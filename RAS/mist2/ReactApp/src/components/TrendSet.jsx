import React from "react";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import { channelLabel, deviceOfPv, devices, pvInfo } from "../registry";
import { roleWord, trendGraph } from "../roles";
import { spansDecades } from "./fields/format";
import Trend from "./Trend";

// What a trend line is called: the device, and the channel if it has one.
export const pvLegend = (name) => {
  const id = deviceOfPv(name);
  const { channel } = pvInfo(name);
  return channel ? (channelLabel(id, channel) ?? `${devices[id].name} ${channel}`) : devices[id].name;
};

// A line of a graph that holds more than one role names its role too.
const lineLegend = (name, group) =>
  new Set(group.map((pv) => pvInfo(pv).role)).size > 1
    ? `${pvLegend(name)}, ${roleWord(pvInfo(name).role)}`
    : pvLegend(name);

// Time-stamped trends of some read-backs, updated on monitors: one graph per
// role and unit (units compared without case: torr and Torr are one), units
// that span decades on a log scale; a set point in the graph of its
// read-back (roles.js). `size` is the grid width of a graph, `redraw` the
// time between two redraws in ms.
const TrendSet = ({ pvs, size = { xs: 12, lg: 6 }, height = 260, redraw }) => {
  const groups = Object.values(
    Object.groupBy(pvs, (name) => `${trendGraph(pvInfo(name).role)}|${(pvInfo(name).egu ?? "").toLowerCase()}`)
  );
  return (
    <Grid container spacing={1}>
      {groups.map((group) => {
        const { role, egu } = pvInfo(group[0]);
        return (
          <Grid key={group.join()} size={size}>
            <Paper variant="outlined" sx={{ p: 1 }} data-trend={group.join(" ")}>
              <Typography variant="subtitle2">
                {roleWord(trendGraph(role))}
                {egu ? ` (${egu})` : ""}
              </Typography>
              <Trend
                pvs={group}
                legend={group.map((name) => lineLegend(name, group))}
                log={spansDecades(egu)}
                height={height}
                redraw={redraw}
              />
            </Paper>
          </Grid>
        );
      })}
    </Grid>
  );
};

export default TrendSet;
