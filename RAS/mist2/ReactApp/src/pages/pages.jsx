import React from "react";
import { alarmPvs, devices, subsystemPages } from "../registry";
import { overview, pageAlarmPvs } from "../synoptic/layout";
import Synoptic from "../synoptic/Synoptic";
import InfrastructurePage from "./InfrastructurePage";
import SubsystemPage from "./SubsystemPage";
import TrendsPage from "./TrendsPage";

export const allAlarmPvs = Object.keys(devices).flatMap((id) => alarmPvs(id));
const slugOf = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-");

// The pages of the GUI, each a tab of the main window that can also stand in
// a window of its own (/page/<slug>): name, the records of its worst alarm
// state, and its content. `height` is the height the Overview drawing fills.
export const pages = [
  { name: overview, alarms: pageAlarmPvs(overview), content: (height) => <Synoptic page={overview} height={height} /> },
  ...subsystemPages.map((page) => ({ name: page, alarms: pageAlarmPvs(page), content: () => <SubsystemPage page={page} /> })),
  { name: "Trends", content: () => <TrendsPage /> },
  { name: "Infrastructure", alarms: allAlarmPvs, content: () => <InfrastructurePage /> },
].map((page) => ({ ...page, slug: slugOf(page.name) }));
