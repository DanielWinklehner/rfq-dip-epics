import React from "react";
import { useTheme } from "@mui/material/styles";
import { drawingOf, elementsOf } from "./layout";
import Statics from "./Statics";
import Symbol from "./Symbol";
import Tag, { tagHeight } from "./Tag";

// The point of a tag nearest to its symbol or anchor, where the leader ends.
const nearest = ([x, y], tag, height) => [
  Math.min(Math.max(x, tag.x), tag.x + tag.w),
  Math.min(Math.max(y, tag.y), tag.y + height),
];

// A drawing of config/drawings.json with its elements: symbols and tags that
// are live and open the device window on a click. Leaders first, then the
// symbols, then the tags, so that a leader that crosses a tag runs below it.
const Synoptic = ({ page, height }) => {
  const theme = useTheme();
  const drawing = drawingOf(page);
  const elements = elementsOf(page);
  return (
    <svg
      viewBox={drawing.viewBox.join(" ")}
      style={{ width: "100%", height, display: "block" }}
      fontFamily={theme.typography.fontFamily}
      data-page={page}
    >
      <Statics items={drawing.statics ?? []} />
      {elements.map(({ device, channel, symbol, anchor, tag }, index) => {
        const from = symbol ? [symbol.x, symbol.y] : anchor;
        return (
          from &&
          tag && (
            <polyline
              key={index}
              points={[from, nearest(from, tag, tagHeight(device, channel))].join(" ")}
              stroke={theme.palette.text.disabled}
              strokeDasharray="2 3"
              fill="none"
            />
          )
        );
      })}
      {elements.map(
        ({ device, channel, symbol }, index) =>
          symbol && <Symbol key={index} id={device} channel={channel} {...symbol} />
      )}
      {elements.map(
        ({ device, channel, tag }, index) => tag && <Tag key={index} id={device} channel={channel} {...tag} />
      )}
    </svg>
  );
};

export default Synoptic;
