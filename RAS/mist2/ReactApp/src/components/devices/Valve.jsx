import React from "react";
import Channels from "./Channels";

// One row per channel: the request beside the read-back of the box. A channel
// without a label in the registry is unused (owner's answer: 5 to 8 spare).
const Valve = ({ id }) => (
  <Channels id={id} rows={[["cmd", "state"]]} unlabelled={(channel) => `${channel} · spare`} />
);

export default Valve;
