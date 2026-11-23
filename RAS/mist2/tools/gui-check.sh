#!/usr/bin/env bash
# Checks the MIST-2 GUI against the running emulation (brief T11, "Checks").
# Needs the emulation (make -C emulation up) and the GUI stack (make -C RAS/mist2
# dev-up). Uses a headless Chromium in the Playwright image, the simulators'
# control interface and Channel Access from the emulation's tools container.
# The script stops and starts the HV IOC container once and leaves everything
# as it found it: faults cleared, the vent valve closed, every AU output off.
#
#   1  every page and device window loads without a JavaScript error or warning
#   2  every device record is shown with the value Channel Access reads
#   3  a silent simulator: its PVs INVALID, the tabs the worst state, the rest
#      unchanged, and back after the fault is cleared
#   4  a stopped IOC: its PVs "no connection", the banner says so, and back
#   5  a set point typed in arrives, the vent valve opens through the
#      confirmation dialog, an output switches on without one, an open door
#      switches it off and clears the request (the switch shows it), closing the
#      door brings nothing back, switching on again works, ALL HV OFF works
#   6  no PV name or PV prefix of the registry in the application sources
#   7  the loop: PID requested with the supplies off is refused and the reason
#      is on the screen; with its permits fulfilled PID from its tag; a set
#      point typed in its window arrives; MANUAL again; everything restored
#   8  values set in place on the Overview: a set point typed into a tag
#      arrives, an unsent entry is given up with Escape, an output switches on
#      and off from its tag, the vent valve asks first from its tag
#   9  tabs as windows: a page opened in a window of its own shows the values
#      Channel Access reads, its tab is marked and brings it to the front,
#      "attach" and closing bring it back, the windows close with the main window
#  10  the data logger (and any service with a role `alive`): its chip in the
#      strip, its widget on the Infrastructure page, on no drawing; in the state
#      Channel Access reads, and when no logger runs also alive, with a stand-in
#      counting in its place for 90 s
# Screenshots go to tools/screenshots/. Exit code 1 on any failure.
set -uo pipefail
cd "$(dirname "$0")/.."
here=$PWD
repo=$(cd ../.. && pwd)
set -a; . ./.env; set +a
url="http://127.0.0.1:$RAS_HTTP_PORT"
emulation=(docker compose -f "$repo/emulation/compose.yaml")
registry=ReactApp/src/registry/registry.json
shots=tools/screenshots
playwright_image=mcr.microsoft.com/playwright:v1.59.1-noble

# A value of the registry's devices (d), and the PV of a device's role.
reg() { python3 -c "import json; d = json.load(open('$registry'))['devices']; print($1)"; }
role() { reg "d['$1']['roles']['$2']"; }

# The devices and the IOC the fault checks use, by registry id.
fault_devices="thermo_hv au_lens2"
stopped_ioc=ioc_hv
# The loop the loop check switches, and the supplies its permits ask to be on.
loop=dis_loop
loop_supplies="fil_heat fil_dis_old"
loop_actuator=fil_heat
# Records of the stopped IOC still expected unprocessed (INVALID, UDF) right
# after its start: they may show INVALID then. Every record that is INVALID/UDF
# at that moment is named in a note.
udf_after_start=""   # none: the loop's mode request is processed at the start now (loop.db, PINI)

failed=0
step() { echo; echo "== $*"; }
result() { if [ "$1" -ne 0 ]; then failed=1; fi; }

ca() {
    # Compose reports the container it creates on stderr; errors pass through.
    "${emulation[@]}" --profile tools run --rm -T tools python3 RAS/mist2/tools/gui_check_ca.py "$@" \
        2> >(grep -v "Container mist2emu-tools-run" >&2)
}

faults=""
ioc_container=""
ilk_sim=""
door=""
restore=()   # "PV value" pairs the loop check writes back at the end
# Work files inside the repository, which the tools container sees at /repo.
work=$(mktemp -d "$here/tools/.work.XXXXXX")
cwork=/repo/RAS/mist2/tools/$(basename "$work")
cleanup() {
    [ -n "$faults" ] && ca clear $faults >/dev/null 2>&1
    [ -n "$ilk_sim" ] && ca release "$ilk_sim" "$door" >/dev/null 2>&1
    [ -n "$ioc_container" ] && docker start "$ioc_container" >/dev/null 2>&1
    for pair in "${restore[@]}"; do ca put $pair >/dev/null 2>&1; done
    rm -rf "$work"
}
trap cleanup EXIT

browser() {
    docker run --rm --network host --user "$(id -u):$(id -g)" -e HOME=/tmp \
        -v "$work:/work" -v "$here/$shots:/shots" -v "$here/tools/gui-check.mjs:/check/gui-check.mjs:ro" \
        -v "$here/$registry:/check/registry.json:ro" -v "$work/node_modules:/check/node_modules:ro" \
        "$playwright_image" node /check/gui-check.mjs "$1" "$url" /work /shots /check/registry.json "${@:2}"
}

# ---- Preconditions ----------------------------------------------------------
if ! curl -sf -o /dev/null "$url/"; then
    echo "gui-check: the GUI does not answer at $url, run 'make -C RAS/mist2 dev-up'" >&2
    exit 1
fi
for service in ioc-rack ioc-hv sim-rack sim-hv; do
    if [ -z "$("${emulation[@]}" ps -q --status running "$service")" ]; then
        echo "gui-check: emulation service $service is not running, run 'make -C emulation up'" >&2
        exit 1
    fi
done
ioc_service=$(python3 -c "import json; print(json.load(open('$registry'))['iocs']['$stopped_ioc']['container'])")
ioc_container=$("${emulation[@]}" ps -q "$ioc_service")
faults=$(python3 -c "
import json; d = json.load(open('$registry'))['devices']
print(' '.join(s for i in '$fault_devices'.split() for s in d[i]['simulators']))")

# Playwright for Node, from the GUI's own node_modules (the node_cache image).
docker run --rm --user "$(id -u):$(id -g)" -v "$work:/out" mist2ras-node-cache sh -c \
    'cp -rL "$(dirname "$(readlink -f /ReactApp/node_modules/playwright)")" /out/node_modules' || exit 1
mkdir -p "$shots"
rm -f "$shots"/*.png

# Vite bundles dependencies on first use; load every route once before checking.
docker run --rm --network host -v "$work/node_modules:/check/node_modules:ro" "$playwright_image" \
    node -e "
const { chromium } = require('/check/node_modules/playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  for (const path of ['/', '/device/valves', '/?tab=trends', '/Probe']) { await p.goto('$url' + path); await p.waitForTimeout(4000); }
  await b.close();
})();" >/dev/null 2>&1

# ---- 1, 2: pages, device windows, values -------------------------------------
step "1, 2: every page and device window, values against Channel Access"
ca read "$cwork/ca-a.json"
browser normal; result $?
ca read "$cwork/ca-b.json"
ca compare "$cwork/ca-a.json" "$cwork/ca-b.json" "$cwork/normal.json"; result $?

# ---- 3: a silent simulator ----------------------------------------------------
step "3: silent simulators ($faults)"
ca fault $faults; sleep 5
browser fault $faults; result $?
ca clear $faults; sleep 5
browser recovered; result $?

# ---- 4: a stopped IOC -----------------------------------------------------------
step "4: IOC $stopped_ioc stopped"
docker stop "$ioc_container" >/dev/null; sleep 3
browser iocdown "$stopped_ioc"; result $?
docker start "$ioc_container" >/dev/null
for _ in $(seq 1 60); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$ioc_container")" = healthy ] && break
    sleep 1
done
sleep 8   # pvServer reconnects; the IOC takes no set point in its first 5 s (P20)
ca read "$cwork/ca-r.json"
browser recovered ca-r.json $udf_after_start; result $?

# ---- 5: writes ------------------------------------------------------------------
step "5: set point, confirmation, output, ALL HV OFF"
browser setpoint mfc sp_cmd; result $?
read -r echo_pv value < "$work/setpoint.txt"
ca wait "$echo_pv" "$value" 15; result $?
vent=$(python3 -c "import json; print(json.load(open('$registry'))['devices']['valves']['channels']['s3']['roles']['state'])")
browser command valves s3 cmd 1 dialog; result $?
ca wait "$vent" 1 15; result $?
browser command valves s3 cmd 0 nodialog; result $?
ca wait "$vent" 0 15; result $?
state=$(python3 -c "import json; print(json.load(open('$registry'))['devices']['au_src']['roles']['out_state'])")
request=$(python3 -c "import json; print(json.load(open('$registry'))['devices']['au_src']['roles']['out_cmd'])")
browser command au_src - out_cmd 1 nodialog; result $?
ca wait "$state" ON 15; result $?

step "5b: the permit latches"
read -r ilk_sim door permit < <(python3 -c "
import json; d = json.load(open('$registry'))['devices']['ilk_old']
print(d['simulators'][0], sorted(d['channels'])[0], d['roles']['open'])")
ca set "$ilk_sim" "$door" 0; result $?
ca wait "$permit" 1 10; result $?
ca wait "$state" OFF 10; result $?
ca wait "$request" DISABLED 10; result $?
browser shows au_src out_cmd 0; result $?
ca release "$ilk_sim" "$door"; result $?
ca wait "$permit" 0 10; result $?
ca hold "$state" OFF 8; result $?
ca hold "$request" DISABLED 1; result $?
browser command au_src - out_cmd 1 nodialog; result $?
ca wait "$state" ON 15; result $?
browser alloff; result $?
ca wait "$state" OFF 15; result $?
ca wait "$request" DISABLED 15; result $?

# ---- 7: the loop ------------------------------------------------------------------
step "7: the loop $loop: a refusal, PID, a set point, MANUAL"
mode_get=$(role $loop mode)
# What the check changes, and how it was: written back at the end, also on an abort.
for pv in $(role $loop mode_cmd) $(role $loop sp_cmd) $(role $loop_actuator iset) \
          $(for id in $loop_supplies; do role $id out_cmd; done); do
    restore=("$pv $(ca get "$pv")" "${restore[@]}")
done
printf '  as found: %s\n' "${restore[@]}"
browser loop $loop refuse; result $?
middle=$(python3 -c "print(round(($(ca get "$(role $loop outmin)") + $(ca get "$(role $loop outmax)")) / 2, 2))")
ca put "$(role $loop_actuator iset)" "$middle"; result $?
for id in $loop_supplies; do ca put "$(role $id out_cmd)" 1; result $?; done
for permit in permit1 permit2 permit3; do ca wait "$(role $loop $permit)" fulfilled 10; result $?; done
browser loop $loop pid; result $?
read -r sp_pv value < "$work/setpoint.txt"
ca wait "$sp_pv" "$value" 5; result $?
ca wait "$mode_get" MANUAL 5; result $?
for pair in "${restore[@]}"; do ca put $pair; result $?; done
restore=()

# ---- 8: values set in place ---------------------------------------------------------
step "8: values set in place on the Overview"
echo_pv=$(reg "d['mfc']['pvs'][d['mfc']['roles']['sp_cmd']]['readback']")
before=$(ca get "$echo_pv")
browser tagsetpoint overview mfc sp_cmd escape; result $?
ca hold "$echo_pv" "$before" 3; result $?
browser tagsetpoint overview mfc sp_cmd enter; result $?
read -r echo_pv value < "$work/setpoint.txt"
ca wait "$echo_pv" "$value" 15; result $?
browser tagcommand overview au_src - out_cmd 1 nodialog; result $?
ca wait "$state" ON 15; result $?
browser tagcommand overview au_src - out_cmd 0 nodialog; result $?
ca wait "$state" OFF 15; result $?
ca wait "$request" DISABLED 15; result $?
browser tagcommand overview valves s3 cmd 1 dialog; result $?
ca wait "$vent" 1 15; result $?
browser tagcommand overview valves s3 cmd 0 nodialog; result $?
ca wait "$vent" 0 15; result $?

# ---- 9: tabs as windows ----------------------------------------------------------------
step "9: a page in a window of its own"
ca read "$cwork/ca-a.json"
browser windows plasma-generator; result $?
ca read "$cwork/ca-b.json"
ca compare "$cwork/ca-a.json" "$cwork/ca-b.json" "$cwork/window.json"; result $?

# ---- 10: the data logger -----------------------------------------------------------
step "10: the data logger"
alive_pv=$(role logger alive)
count_pv=$(role logger count)
alive=$(python3 -c "print(int(float('$(ca get "$alive_pv")')))")
browser logger "$alive"; result $?
if [ "$alive" != 1 ]; then
    # No logger runs (the emulation alone): a stand-in counts in its place for
    # 90 s, so the check sees the live state too, then the counter is put
    # back and the logger is dead again.
    count=$(ca get "$count_pv")
    ca beat "$count_pv" 90 >/dev/null & beat=$!
    ca wait "$alive_pv" 1 10; result $?
    browser logger 1; result $?
    wait $beat
    ca put "$count_pv" "$count" >/dev/null
    ca wait "$alive_pv" 0 15; result $?
fi

# ---- 6: no PV names in the sources ---------------------------------------------
step "6: no PV name or prefix in the application sources"
python3 - "$registry" ReactApp/src <<'EOF'; result $?
import json, pathlib, re, sys
registry = json.load(open(sys.argv[1]))
names = {n for ioc in registry["iocs"].values() for n in ioc["pvs"]}
names |= {n for d in registry["devices"].values() for n in d["pvs"]}
prefixes = {re.split(r"[:]", n)[0] for n in names if ":" in n}
patterns = [re.escape(n) for n in names] + [re.escape(p) + r"[:$\"'`]" for p in prefixes]
pattern = re.compile("|".join(sorted(patterns, key=len, reverse=True)))
hits = []
files = [f for f in pathlib.Path(sys.argv[2]).rglob("*") if f.is_file() and "registry" not in f.parts]
for f in files:
    for number, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
        if pattern.search(line):
            hits.append(f"{f}:{number}: {line.strip()}")
print("\n".join(f"FAIL {h}" for h in hits) or
      f"PASS {len(files)} files, none contains one of {len(names)} PV names or {len(prefixes)} prefixes")
sys.exit(1 if hits else 0)
EOF

echo
if [ $failed -eq 0 ]; then echo "gui-check: PASS"; else echo "gui-check: FAIL"; fi
exit $failed
