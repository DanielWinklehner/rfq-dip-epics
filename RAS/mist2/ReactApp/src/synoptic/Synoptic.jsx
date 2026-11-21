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
// are live and open the device window on a click.
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
          <g key={index}>
            {from && tag && (
              <polyline
                points={[from, nearest(from, tag, tagHeight(device, channel))].join(" ")}
                stroke={theme.palette.text.disabled}
                strokeDasharray="2 3"
                fill="none"
              />
            )}
            {symbol && <Symbol id={device} channel={channel} {...symbol} />}
            {tag && <Tag id={device} channel={channel} {...tag} />}
          </g>
        );
      })}
    </svg>
  );
};

export default Synoptic;
