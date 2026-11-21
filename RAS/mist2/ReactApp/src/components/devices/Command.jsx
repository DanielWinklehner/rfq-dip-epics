import React from "react";
import { devices, rolesOf } from "../../registry";
import PvAction from "../fields/PvAction";

const Command = ({ id, size }) => (
  <PvAction pv={rolesOf(id).cmd} label={devices[id].name.toUpperCase()} size={size} />
);

export default Command;
