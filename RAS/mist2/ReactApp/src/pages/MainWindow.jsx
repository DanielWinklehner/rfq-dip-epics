import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import OpenInNew from "@mui/icons-material/OpenInNew";
import TraditionalLayout from "React-Automation-Studio/components/UI/Layout/ComposedLayouts/TraditionalLayout";
import { AlarmDot } from "../alarm/AlarmMarks";
import { AlarmProvider, useWorstAlarm } from "../alarm/AlarmStore";
import Command from "../components/devices/Command";
import StatusStrip from "../components/StatusStrip";
import { devices, installedDevices } from "../registry";
import { isPageOut, openPageWindow } from "../windows";
import { allAlarmPvs, pages } from "./pages";

const Dot = ({ alarms }) => <AlarmDot state={useWorstAlarm(alarms)} />;

// A tab: the page's name, its worst state and the control that opens it in a
// window of its own. While the page is out the control is filled and the
// name in italics. (A span, not a button: the tab itself is a button.)
const TabLabel = ({ page, out }) => (
  <Stack direction="row" alignItems="center" data-tab={page.slug} data-out={out ? "true" : undefined}>
    <Box component="span" sx={{ fontStyle: out ? "italic" : undefined }}>
      {page.name}
    </Box>
    {page.alarms && <Dot alarms={page.alarms} />}
    <Box
      component="span"
      role="button"
      aria-label={`${page.name} in a window of its own`}
      title={out ? "Open in a window of its own: bring it to the front" : "Open in a window of its own"}
      data-popout
      onClick={(event) => {
        event.stopPropagation();
        openPageWindow(page.slug);
      }}
      sx={{
        display: "inline-flex",
        ml: 0.75,
        p: 0.25,
        borderRadius: 1,
        color: out ? "primary.contrastText" : "text.disabled",
        background: (theme) => (out ? theme.palette.primary.main : "none"),
        "&:hover": { color: "text.primary" },
      }}
    >
      <OpenInNew sx={{ fontSize: 14 }} />
    </Box>
  </Stack>
);

// What the main window shows of a page that is out.
const PageOut = ({ page }) => (
  <Stack spacing={1} alignItems="flex-start" sx={{ p: 3 }} data-page-out={page.slug}>
    <Typography>{page.name} is open in a window of its own.</Typography>
    <Button variant="outlined" size="small" onClick={() => openPageWindow(page.slug)}>
      Bring it to the front
    </Button>
  </Stack>
);

const commands = installedDevices().filter((id) => devices[id].class === "command");
const checkEvery = 500; // ms

// The main window: app bar with the tabs, the commands that must always be
// reachable and the place of the PDF report (WP8); below it the status strip
// and the pages. Pages stay mounted while hidden, so trends keep their history.
// A page that is out in a window of its own is not mounted here; when its
// window closes ("attach" or the browser's button) the main window shows it.
const MainWindow = () => {
  const [params, setParams] = useSearchParams();
  const [out, setOut] = useState([]);
  const index = Math.max(0, pages.findIndex((page) => page.slug === params.get("tab")));
  useEffect(() => {
    window.dispatchEvent(new Event("resize"));
  }, [index]);
  // Which pages are out: asked of their windows, from a timer.
  const outRef = useRef(out);
  useEffect(() => {
    const timer = setInterval(() => {
      const before = outRef.current;
      const now = pages.map((page) => page.slug).filter(isPageOut);
      if (before.join() === now.join()) return;
      outRef.current = now;
      setOut(now);
      const back = before.find((slug) => !now.includes(slug));
      if (back) setParams({ tab: back });
    }, checkEvery);
    return () => clearInterval(timer);
  }, [setParams]);
  const appBar = (
    <Box component="span" sx={{ display: "flex", alignItems: "center", gap: 2, width: "100%", whiteSpace: "nowrap" }}>
      <Box component="span" sx={{ flexShrink: 0 }}>
        MIST-2
      </Box>
      <Tabs
        value={index}
        onChange={(event, value) =>
          out.includes(pages[value].slug) ? openPageWindow(pages[value].slug) : setParams({ tab: pages[value].slug })
        }
        textColor="inherit"
        variant="scrollable"
        sx={{ flexGrow: 1, minWidth: 0 }}
      >
        {pages.map((page) => (
          <Tab
            key={page.slug}
            sx={{ textTransform: "none", minWidth: 0, px: 1.5 }}
            label={<TabLabel page={page} out={out.includes(page.slug)} />}
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
      <TraditionalLayout title={appBar} denseAppBar>
        <Box sx={{ position: "sticky", top: 48, zIndex: (theme) => theme.zIndex.appBar - 1 }}>
          <StatusStrip title="MIST-2" />
        </Box>
        {pages.map((page, i) => (
          <Box key={page.slug} hidden={i !== index} data-page-tab={page.slug}>
            {out.includes(page.slug) ? <PageOut page={page} /> : page.content("calc(100vh - 100px)")}
          </Box>
        ))}
      </TraditionalLayout>
    </AlarmProvider>
  );
};

export default MainWindow;
