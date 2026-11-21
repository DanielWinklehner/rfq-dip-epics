import React from "react";
import Grid from "@mui/material/Grid";
import { rolesOf } from "../../registry";
import RoleField from "../RoleField";

// Rows of role fields, two per row so that related roles stand side by side.
// A row whose roles the device or channel does not have is left out, a single
// missing role leaves its place empty.
const RoleGrid = ({ id, channel, rows, fieldProps = {} }) => {
  const roles = rolesOf(id, channel);
  return (
    <Grid container spacing={2} alignItems="flex-start">
      {rows
        .filter((row) => row.some((role) => roles[role]))
        .flat()
        .map((role, index) => (
          <Grid key={`${role}-${index}`} size={6}>
            <RoleField id={id} channel={channel} role={role} {...fieldProps[role]} />
          </Grid>
        ))}
    </Grid>
  );
};

export default RoleGrid;
