import React from "react";
import { useTheme } from "@mui/material/styles";

// The parts of a drawing that are no device: chamber, flanges, beam axis,
// lines and labels. Each item of the data is one SVG element.
const Statics = ({ items }) => {
  const theme = useTheme();
  const stroke = theme.palette.text.secondary;
  const styles = {
    solid: { stroke, fill: "none", strokeWidth: 2 },
    dashed: { stroke, fill: "none", strokeWidth: 1.5, strokeDasharray: "8 5" },
    body: { stroke, fill: theme.palette.action.hover, strokeWidth: 2 },
    beam: { stroke: theme.palette.primary.main, fill: "none", strokeWidth: 2, strokeDasharray: "12 6" },
    pipe: { stroke, fill: "none", strokeWidth: 4 },
    thin: { stroke, fill: "none", strokeWidth: 1, strokeDasharray: "2 3" },
  };
  return items.map((item, index) => {
    const style = styles[item.style ?? "solid"];
    switch (item.type) {
      case "rect":
        return <rect key={index} x={item.x} y={item.y} width={item.w} height={item.h} rx={item.rx} {...style} />;
      case "circle":
        return <circle key={index} cx={item.x} cy={item.y} r={item.r} {...style} />;
      case "line":
        return <polyline key={index} points={item.points.join(" ")} {...style} />;
      case "polygon":
        return <polygon key={index} points={item.points.join(" ")} {...style} />;
      default:
        return (
          <text
            key={index}
            x={item.x}
            y={item.y}
            fontSize={item.size ?? 12}
            textAnchor={item.anchor ?? "start"}
            fontStyle={item.italic ? "italic" : undefined}
            fill={item.muted ? theme.palette.text.disabled : theme.palette.text.secondary}
          >
            {item.text}
          </text>
        );
    }
  });
};

export default Statics;
