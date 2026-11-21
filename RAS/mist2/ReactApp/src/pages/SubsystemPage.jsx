import React from "react";
import Stack from "@mui/material/Stack";
import Flags from "../components/Flags";
import TrendSet from "../components/TrendSet";
import { devices } from "../registry";
import { trendPvs } from "../roles";
import { elementsOf } from "../synoptic/layout";
import Synoptic from "../synoptic/Synoptic";

// A subsystem tab: the drawing of the subsystem (or the generated list of its
// devices), what the registry flags about them, and the trends of its own
// devices (copies from other pages, such as the MFC, are not trended twice).
const SubsystemPage = ({ page }) => {
  const elements = elementsOf(page);
  const flagged = [...new Set(elements.map((e) => e.device))].filter(
    (id) => Object.keys(devices[id].flags).length > 0
  );
  const trends = [
    ...new Set(
      elements
        .filter((e) => devices[e.device].page === page)
        .flatMap((e) => trendPvs(e.device, e.channel))
    ),
  ];
  return (
    <Stack spacing={1} sx={{ p: 1 }}>
      <Synoptic page={page} />
      <Stack spacing={0.5}>
        {flagged.map((id) => (
          <Flags key={id} id={id} />
        ))}
      </Stack>
      <TrendSet pvs={trends} />
    </Stack>
  );
};

export default SubsystemPage;
