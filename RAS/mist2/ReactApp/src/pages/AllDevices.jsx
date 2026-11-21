import React from "react";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Typography from "@mui/material/Typography";
import TraditionalLayout from "React-Automation-Studio/components/UI/Layout/ComposedLayouts/TraditionalLayout";
import { devices, installedDevices } from "../registry";
import { widgetOf } from "../components/devices";
import Flags from "../components/Flags";

const AllDevices = () => (
  <TraditionalLayout title="MIST-2" denseAppBar>
    <Grid container spacing={2} sx={{ p: 2 }}>
      {installedDevices().map((id) => {
        const Widget = widgetOf(devices[id].class);
        return (
          <Grid key={id} size={4}>
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="h6">{devices[id].name}</Typography>
              <Flags id={id} />
              <Widget id={id} />
            </Paper>
          </Grid>
        );
      })}
    </Grid>
  </TraditionalLayout>
);

export default AllDevices;
