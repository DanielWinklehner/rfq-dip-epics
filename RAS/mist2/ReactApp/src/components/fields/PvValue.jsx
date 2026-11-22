import React from "react";
import Box from "@mui/material/Box";
import TextField from "@mui/material/TextField";
import { useTheme } from "@mui/material/styles";
import { fieldSx } from "../../alarm/severity";
import useReading from "./useReading";

// A read-back: its word, or value and unit from the record, coloured by its
// severity. `words` are the registry's words for the values.
const PvValue = ({ pv, label, words }) => {
  const theme = useTheme();
  const { state, text, menu, openMenu } = useReading(pv, words);
  return (
    <Box onContextMenu={openMenu}>
      <TextField
        size="small"
        label={label}
        value={text}
        sx={fieldSx(theme, state)}
        slotProps={{
          input: { readOnly: true },
          htmlInput: { "data-pv": pv, "data-alarm": state },
        }}
      />
      {menu}
    </Box>
  );
};

export default PvValue;
