import React from "react";
import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import TraditionalLayout from "React-Automation-Studio/components/UI/Layout/ComposedLayouts/TraditionalLayout";
import TextOutput from "React-Automation-Studio/components/BaseComponents/TextOutput";

// The test records that each emulated IOC serves (DESIGN.md section 2):
// $(ioc):heartbeat counts up once per second, $(ioc):mode is "sim" or "real".
// TextOutput colors its field by EPICS alarm severity (alarmSensitive) and
// shows the PV name with a disconnected icon while the PV is not connected.
const iocs = [
  { title: "Rack IOC", ioc: "IOC-RACK" },
  { title: "Platform IOC", ioc: "IOC-HV" },
];

const Mist2Main = () => (
  <TraditionalLayout title="MIST-2" denseAppBar alignTitle="center">
    <Grid container spacing={2} sx={{ padding: 2 }}>
      {iocs.map(({ title, ioc }) => (
        <Grid key={ioc} size={{ xs: 12, md: 6 }}>
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
          <Grid container spacing={2}>
            <Grid size={6}>
              <TextOutput
                pv="$(ioc):heartbeat"
                macros={{ "$(ioc)": ioc }}
                label="heartbeat"
                alarmSensitive
              />
            </Grid>
            <Grid size={6}>
              <TextOutput
                pv="$(ioc):mode"
                macros={{ "$(ioc)": ioc }}
                label="mode"
                useStringValue
                alarmSensitive
              />
            </Grid>
          </Grid>
        </Grid>
      ))}
    </Grid>
  </TraditionalLayout>
);

export default Mist2Main;
