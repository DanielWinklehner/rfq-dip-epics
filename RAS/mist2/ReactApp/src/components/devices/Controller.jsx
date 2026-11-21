import React from "react";
import RoleGrid from "./RoleGrid";

// A controller that serves other devices (registry class null): its identity.
const Controller = ({ id }) => <RoleGrid id={id} rows={[["id", "firmware"]]} />;

export default Controller;
