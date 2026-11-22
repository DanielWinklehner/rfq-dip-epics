import React from "react";
import { useParams } from "react-router-dom";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CssBaseline from "@mui/material/CssBaseline";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { AlarmChip } from "../alarm/AlarmMarks";
import { AlarmProvider, useWorstAlarm } from "../alarm/AlarmStore";
import StatusStrip from "../components/StatusStrip";
import { attachPage } from "../windows";
import { pages } from "./pages";

const PageChip = ({ alarms }) => <AlarmChip state={useWorstAlarm(alarms)} />;

// A tab of the main window in a browser window of its own (owner's wish of
// 2026-11-22): the page's name, its own severity and "attach", the status
// strip with the emulator banner, then the page. An ordinary route,
// /page/<slug>, so it can be opened by its address as well.
const PageWindow = () => {
  const { slug } = useParams();
  const page = pages.find((p) => p.slug === slug);
  if (!page) return <Typography sx={{ p: 2 }}>No page {slug}.</Typography>;
  return (
    <AlarmProvider pvs={page.alarms ?? []}>
      <CssBaseline />
      <StatusStrip title={page.name} />
      <Stack direction="row" spacing={2} alignItems="center" sx={{ px: 1.5, py: 0.5 }}>
        <Typography variant="h6" data-page-name>
          {page.name}
        </Typography>
        {page.alarms && <PageChip alarms={page.alarms} />}
        <Box sx={{ flexGrow: 1 }} />
        <Button variant="outlined" size="small" onClick={() => attachPage(slug)} data-attach>
          Attach to the main window
        </Button>
      </Stack>
      <Box data-page-tab={slug}>{page.content("calc(100vh - 110px)")}</Box>
    </AlarmProvider>
  );
};

export default PageWindow;
