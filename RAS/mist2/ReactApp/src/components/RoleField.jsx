import React from "react";
import { pvInfo, rolesOf, wordsOf } from "../registry";
import { roleText } from "../roles";
import PvCommand from "./fields/PvCommand";
import PvLamp from "./fields/PvLamp";
import PvSetpoint from "./fields/PvSetpoint";
import PvValue from "./fields/PvValue";

// The field for one role of a device or channel, chosen by the record and
// the registry: a binary request gets buttons (asking first where the
// registry says `confirm`), any other written record an input field, a
// read-back with two words a lamp, everything else a value field. Nothing when
// the device does not have the role. The registry's notes are in the expert view.
// `dense` gives the written fields their tag form, with `label` from the tag.
const RoleField = ({ id, channel, role, dense, label }) => {
  const pv = rolesOf(id, channel)[role];
  if (!pv) return null;
  const { type, access, confirm } = pvInfo(pv);
  const words = wordsOf(id, channel, role);
  const props = { pv, label: label ?? roleText(id, role, channel) };
  if (access === "w") {
    return type === "bo" ? (
      <PvCommand {...props} custom_selection_strings={words} confirm={confirm} dense={dense} />
    ) : (
      <PvSetpoint {...props} dense={dense} />
    );
  }
  if (words?.length === 2) return <PvLamp {...props} words={words} />;
  return <PvValue {...props} words={words} />;
};

export default RoleField;
