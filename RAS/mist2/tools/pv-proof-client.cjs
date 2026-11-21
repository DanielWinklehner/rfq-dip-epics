// Reads PVs through pvServer's own client interface: the Socket.IO namespace
// /pvServer behind nginx, with the same messages that RAS's EpicsPV.tsx sends.
// Runs in the mist2ras-node-cache image (socket.io-client from ReactApp).
//
// usage: node pv-proof-client.cjs <url> <seconds> <counter PV>... -- <string PV>...
// A counter PV passes when it delivers at least two different values,
// a string PV when it delivers "sim" or "real". Exit code 1 on any FAIL.
"use strict";
const { io } = require("socket.io-client");

const [url, secondsArg, ...rest] = process.argv.slice(2);
const sep = rest.indexOf("--");
const counters = sep < 0 ? rest : rest.slice(0, sep);
const strings = sep < 0 ? [] : rest.slice(sep + 1);
const seen = {};
for (const pv of [...counters, ...strings]) seen[pv] = { values: [], disconnects: 0 };

const verdict = (pv) => {
  const values = seen[pv].values;
  // Compared as numbers: the first message carries "2", later ones "3.0".
  if (counters.includes(pv)) return new Set(values.map(Number)).size >= 2;
  return values.some((v) => v === "sim" || v === "real");
};
const allPass = () => Object.keys(seen).every(verdict);

const socket = io(url + "/pvServer", { transports: ["websocket"], forceNew: true });
let n = 0;
const subscribe = () => {
  for (const pv of Object.keys(seen)) {
    socket.emit("request_pv_info", {
      data: pv,
      useBinaryValue: false,
      pvConnectionId: "pv-proof-" + ++n,
      clientAuthorisation: "unauthenticated",
    });
  }
};
socket.on("connect", () => {
  console.log(`connected to ${url}/pvServer, socket id ${socket.id}`);
  subscribe();
});
socket.on("connect_error", (e) => console.log(`connect_error: ${e.message}`));
socket.on("redirectToLogIn", () => console.log("pvServer asks for login (VITE_EnableLogin=true?)"));
for (const pv of Object.keys(seen)) {
  socket.on(pv, (msg) => {
    if (msg.connected !== "1") {
      seen[pv].disconnects++;
      return;
    }
    const value = strings.includes(pv) ? String(msg.char_value) : String(msg.value);
    seen[pv].values.push(value);
    console.log(`  ${pv} = ${value} (severity ${msg.severity})`);
    if (allPass()) finish();
  });
}

let done = false;
function finish() {
  if (done) return;
  done = true;
  socket.close();
  console.log("");
  let fail = 0;
  for (const pv of Object.keys(seen)) {
    const ok = verdict(pv);
    if (!ok) fail++;
    const values = seen[pv].values;
    const detail = values.length
      ? `values ${[...new Set(values)].slice(0, 5).join(", ")}`
      : `no value received (${seen[pv].disconnects} disconnected messages)`;
    console.log(`${ok ? "PASS" : "FAIL"} ${pv}: ${detail}`);
  }
  process.exit(fail ? 1 : 0);
}
setTimeout(finish, Number(secondsArg) * 1000);
