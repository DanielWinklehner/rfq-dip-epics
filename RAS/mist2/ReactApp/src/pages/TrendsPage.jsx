import React, { useState } from "react";
import Autocomplete from "@mui/material/Autocomplete";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import TrendSet, { pvLegend } from "../components/TrendSet";
import { deviceOfPv, installedDevices, pvInfo } from "../registry";
import { roleText, trendPvs } from "../roles";

const choices = installedDevices().flatMap((id) => trendPvs(id));
const choiceLabel = (name) => `${pvLegend(name)} · ${roleText(deviceOfPv(name), pvInfo(name).role)} · ${name}`;

// Any read-back of the registry, picked by the operator.
const TrendsPage = () => {
  const [picked, setPicked] = useState([]);
  return (
    <Stack spacing={1} sx={{ p: 1 }}>
      <Autocomplete
        multiple
        options={choices}
        value={picked}
        onChange={(event, value) => setPicked(value)}
        getOptionLabel={choiceLabel}
        renderInput={(params) => <TextField {...params} label="Trend these read-backs" />}
      />
      <TrendSet pvs={picked} size={12} height={380} />
    </Stack>
  );
};

export default TrendsPage;
