import React from "react";
import Grid from "@mui/material/Grid";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { rolesOf } from "../../registry";
import RoleField from "../RoleField";

// Rows of role fields, two per row so that related roles stand side by side.
// A row whose roles the device or channel does not have is left out, a single
// missing role (or null) leaves its place empty. `title` heads the rows when
// any is shown.
const RoleGrid = ({ id, channel, rows, title }) => {
  const roles = rolesOf(id, channel);
  const shown = rows.filter((row) => row.some((role) => roles[role]));
  if (shown.length === 0) return null;
  return (
    <Stack spacing={1}>
      {title && <Typography variant="subtitle2">{title}</Typography>}
      <Grid container spacing={2} alignItems="flex-start">
        {shown.flat().map((role, index) => (
          <Grid key={`${role}-${index}`} size={6}>
            {role && <RoleField id={id} channel={channel} role={role} />}
          </Grid>
        ))}
      </Grid>
    </Stack>
  );
};

export default RoleGrid;
