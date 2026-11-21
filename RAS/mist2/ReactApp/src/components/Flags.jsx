import React from "react";
import Alert from "@mui/material/Alert";
import Stack from "@mui/material/Stack";
import { devices } from "../registry";

// What the registry flags about a device, with its reason, as the GUI must
// show it (brief, requirement 8).
export const flagTitles = {
  assumed: "Runs on assumptions",
  not_installed: "Not installed",
};

const Flags = ({ id }) => (
  <Stack spacing={1}>
    {Object.entries(devices[id].flags).map(([flag, reason]) => (
      <Alert
        key={flag}
        severity="info"
        variant="outlined"
        data-flag={flag}
        sx={{ py: 0 }}
      >
        <strong>{flagTitles[flag] ?? flag}:</strong> {reason}
      </Alert>
    ))}
  </Stack>
);

export default Flags;
