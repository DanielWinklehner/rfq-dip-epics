import React from "react";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { alarmColors } from "../../alarm/severity";
import useReading from "./useReading";

// A value inline in text or a table cell. `field` reads another field of the
// record (VAL$ for the full text of a long string).
const PvText = ({ pv, field }) => {
  const theme = useTheme();
  const { state, text, menu, openMenu } = useReading(pv, undefined, field);
  const colors = alarmColors(theme, state);
  return (
    <Typography
      variant="body2"
      component="span"
      data-pv={pv}
      data-alarm={state}
      onContextMenu={openMenu}
      sx={{
        px: 0.5,
        background: colors.fill,
        outline: state === "ok" ? undefined : `1px ${colors.dashed ? "dashed" : "solid"} ${colors.stroke}`,
        overflowWrap: "anywhere",
      }}
    >
      {text}
      {menu}
    </Typography>
  );
};

export default PvText;
