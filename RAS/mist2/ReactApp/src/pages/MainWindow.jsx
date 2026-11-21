import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import TraditionalLayout from "React-Automation-Studio/components/UI/Layout/ComposedLayouts/TraditionalLayout";
import { AlarmDot } from "../alarm/AlarmMarks";
import { AlarmProvider, useWorstAlarm } from "../alarm/AlarmStore";
import Command from "../components/devices/Command";
import StatusStrip from "../components/StatusStrip";
import { alarmPvs, devices, installedDevices, subsystemPages } from "../registry";
import { overview, pageAlarmPvs } from "../synoptic/layout";
import Synoptic from "../synoptic/Synoptic";
import InfrastructurePage from "./InfrastructurePage";
import SubsystemPage from "./SubsystemPage";
import TrendsPage from "./TrendsPage";

const allAlarmPvs = Object.keys(devices).flatMap((id) => alarmPvs(id));
const slug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-");

const pages = [
  { name: overview, alarms: pageAlarmPvs(overview), content: <Synoptic page={overview} height="calc(100vh - 100px)" /> },
  ...subsystemPages.map((page) => ({ name: page, alarms: pageAlarmPvs(page), content: <SubsystemPage page={page} /> })),
  { name: "Trends", content: <TrendsPage /> },
  { name: "Infrastructure", alarms: allAlarmPvs, content: <InfrastructurePage /> },
];

const TabLabel = ({ name, alarms }) => {
  const state = useWorstAlarm(alarms);
  return (
    <Stack direction="row" alignItems="center" data-tab={slug(name)}>
      {name}
      <AlarmDot state={state} />
    </Stack>
  );
};

const commands = installedDevices().filter((id) => devices[id].class === "command");

// The main window: app bar with the tabs, the commands that must always be
// reachable and the place of the PDF report (WP8); below it the status strip
// and the pages. Pages stay mounted while hidden, so trends keep their history.
const MainWindow = () => {
  const [params, setParams] = useSearchParams();
  const index = Math.max(0, pages.findIndex((page) => slug(page.name) === params.get("tab")));
  useEffect(() => {
    window.dispatchEvent(new Event("resize"));
  }, [index]);
  const appBar = (
    <Box component="span" sx={{ display: "flex", alignItems: "center", gap: 2, width: "100%", whiteSpace: "nowrap" }}>
      <Box component="span" sx={{ flexShrink: 0 }}>
        MIST-2
      </Box>
      <Tabs
        value={index}
        onChange={(event, value) => setParams({ tab: slug(pages[value].name) })}
        textColor="inherit"
        variant="scrollable"
        sx={{ flexGrow: 1, minWidth: 0 }}
      >
        {pages.map((page) => (
          <Tab
            key={page.name}
            sx={{ textTransform: "none", minWidth: 0, px: 1.5 }}
            label={page.alarms ? <TabLabel {...page} /> : page.name}
          />
        ))}
      </Tabs>
      <Box component="span" sx={{ flexShrink: 0 }}>
        {commands.map((id) => (
          <Command key={id} id={id} size="small" />
        ))}
      </Box>
      <Button
        variant="outlined"
        size="small"
        color="inherit"
        disabled
        title="PDF report: work package WP8"
        sx={{ flexShrink: 0 }}
      >
        PDF report
      </Button>
    </Box>
  );
  return (
    <AlarmProvider pvs={allAlarmPvs}>
      <TraditionalLayout title={appBar} denseAppBar hideMoreVertMenu={false}>
        <Box sx={{ position: "sticky", top: 48, zIndex: (theme) => theme.zIndex.appBar - 1 }}>
          <StatusStrip title="MIST-2" />
        </Box>
        {pages.map((page, i) => (
          <Box key={page.name} hidden={i !== index} data-page-tab={slug(page.name)}>
            {page.content}
          </Box>
        ))}
      </TraditionalLayout>
    </AlarmProvider>
  );
};

export default MainWindow;
