import React from "react";
import confirmations from "../config/confirm.json";
import { pvInfo, rolesOf } from "../registry";
import { roleText } from "../roles";
import PvCommand from "./fields/PvCommand";
import PvLamp from "./fields/PvLamp";
import PvSetpoint from "./fields/PvSetpoint";
import PvValue from "./fields/PvValue";

// The field for one role of a device or channel, chosen by the record: a
// binary request gets buttons, any other written record an input field, a
// binary read-back a lamp, everything else a value field. Nothing when the
// device does not have the role. The registry's note is the helper text,
// config/confirm.json says which requests ask first. `lamp` shows a 0/1
// read-back that is not a binary record as a lamp.
const RoleField = ({ id, channel, role, label, lamp = false, ...others }) => {
  const pv = rolesOf(id, channel)[role];
  if (!pv) return null;
  const { type, access, note } = pvInfo(pv);
  const confirm = confirmations.confirm.find(
    (c) => c.device === id && c.channel === channel && c.role === role
  );
  const props = { pv, label: label ?? roleText(id, role), helperText: note, confirm, ...others };
  if (access === "w") return type === "bo" ? <PvCommand {...props} /> : <PvSetpoint {...props} />;
  return type === "bi" || lamp ? <PvLamp {...props} /> : <PvValue {...props} />;
};

export default RoleField;
