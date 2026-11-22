import React from "react";
import Channels from "./Channels";

// One row per channel: the request beside the read-back of the box.
const Valve = ({ id }) => <Channels id={id} rows={[["cmd", "state"]]} />;

export default Valve;
