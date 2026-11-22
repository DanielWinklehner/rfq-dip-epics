import React from "react";
import { useTheme } from "@mui/material/styles";
import { useWorstAlarm } from "../alarm/AlarmStore";
import { alarmColors, marker } from "../alarm/severity";
import Command from "../components/devices/Command";
import { flagTitles } from "../components/Flags";
import { alarmPvs, channelLabel, devices } from "../registry";
import { openDeviceWindow } from "../windows";
import tagRows from "./tagRows";
import TagRow, { heightOf } from "./TagRow";

const headHeight = 22;
const commandHeight = 38;

// The rows of a tag with the offset of each below the head.
const placedRows = (id, channel) => {
  let top = headHeight;
  return tagRows(id, channel).map((row) => {
    const placed = { ...row, top };
    top += heightOf(row);
    return placed;
  });
};

export const tagHeight = (id, channel) =>
  headHeight +
  tagRows(id, channel).reduce((sum, row) => sum + heightOf(row), 0) +
  (devices[id].class === "command" ? commandHeight : 4);

// The tag of a device or of one channel: its name, its worst alarm state, the
// registry's flags and its tag rows, what it sets in place among them. A click
// outside the fields opens the device window.
const Tag = ({ id, channel, x, y, w }) => {
  const theme = useTheme();
  const device = devices[id];
  const state = useWorstAlarm(alarmPvs(id, channel));
  const colors = alarmColors(theme, state);
  const title = channel ? (channelLabel(id, channel) ?? channel) : device.name;
  const flags = Object.keys(device.flags).filter((flag) => flag !== "not_installed");
  const height = tagHeight(id, channel);
  return (
    <g
      onClick={() => openDeviceWindow(id, channel)}
      style={{ cursor: "pointer" }}
      data-device={id}
      data-channel={channel}
      data-alarm={state}
    >
      <title>{Object.entries(device.flags).map(([f, reason]) => `${flagTitles[f]}: ${reason}`).join("\n")}</title>
      <rect
        x={x}
        y={y}
        width={w}
        height={height}
        rx={4}
        fill={theme.palette.background.paper}
        stroke={state === "ok" ? theme.palette.text.disabled : colors.stroke}
        strokeWidth={state === "ok" ? 1 : 2.5}
        strokeDasharray={colors.dashed ? "6 4" : undefined}
      />
      <rect x={x + 1} y={y + 1} width={w - 2} height={headHeight - 2} rx={3} fill={colors.fill} />
      <text x={x + 7} y={y + 15} fontSize={12} fontWeight={700} fill={theme.palette.text.primary}>
        {title} {marker(state)}
      </text>
      {flags.length > 0 && (
        <text x={x + w - 7} y={y + 15} fontSize={10} textAnchor="end" fill={theme.palette.info.main}>
          {flags.join(" · ")}
        </text>
      )}
      {placedRows(id, channel).map((row) => (
        <TagRow key={row.pv} {...row} x={x} y={y + row.top} w={w} />
      ))}
      {device.class === "command" && (
        <foreignObject x={x + 6} y={y + headHeight + 2} width={w - 12} height={commandHeight - 6}>
          <div onClick={(event) => event.stopPropagation()}>
            <Command id={id} size="small" />
          </div>
        </foreignObject>
      )}
    </g>
  );
};

export default Tag;
