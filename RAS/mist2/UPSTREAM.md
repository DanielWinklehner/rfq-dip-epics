# Where RAS/mist2 comes from

## Sources

| What | Repository | Version |
|---|---|---|
| Boilerplate (files copied, no history) | https://github.com/React-Automation-Studio/React-Automation-Studio-Example-Project-1 | commit `c4bf763e067065d8e9bbc74181768f46b9cc869e` (2026-06-01, "Merge pull request #22 from React-Automation-Studio/V8.1.0updates"), which is on RAS V8.1.0 |
| React Automation Studio (git submodule `submodules/React-Automation-Studio`) | https://github.com/React-Automation-Studio/React-Automation-Studio | tag `V8.1.0`, commit `184c0ada7fbb4c5bc476545ba99bb632d6dcbd7e` |

`LICENSE` is the boilerplate's license (MIT). The submodule has its own.
Nothing inside the submodule is modified.

## What was kept from the boilerplate

| File | Change |
|---|---|
| `LICENSE` | none |
| `docker/epicsBase/Dockerfile` | none |
| `docker/node_cache/Dockerfile` | none |
| `docker/pvserver/Dockerfile` | no `EPICS_CA_ADDR_LIST` default in the image: `.env` is the only place for Channel Access settings |
| `docker/frontendserverDev/Dockerfile` | `.env` is no longer copied into the image (Compose passes it as environment, Vite exposes the `VITE_*` variables) |
| `ReactApp/package.json`, `vite.config.js`, `jsconfig.json`, `public/` (icons, `manifest.json`), `index.html`, `src/App.jsx`, `src/main.jsx`, `src/index.css` | title and manifest name set to MIST-2, commented-out service-worker code dropped from `main.jsx` |
| `ReactApp/src/AppRoutes.jsx` | rewritten: one route, `/`, to `src/pages/Mist2Main.jsx` |

New: `compose.dev.yaml` (replaces the boilerplate's five Compose files),
`env.template` (replaces `example.env`), `nginx/mist2.dev.conf.template`
(derived from the submodule's `nginx/nginx.dev.conf`), `Makefile`, `tools/`.

## What was removed, and what it takes to bring it back

The minimum was found by experiment: `pvserver`, `frontend` (Vite) and `nginx`
alone serve the page and deliver PVs (see `tools/pv-proof.sh`). With
`VITE_EnableLogin=false` pvServer never opens a database connection: it only
connects to MongoDB when a client sends a `mongodb://` request or when login is
enabled (`pvServer/userAuthentication/authenticate.py`, `loadKnownDbUsers`).

| Removed | Used for | To bring it back |
|---|---|---|
| `mongo1`, `mongo2`, `mongo3`, `mongosetup` (three-node MongoDB replica set) | every database feature below | Add the `mongo*` and `mongosetup` services from the boilerplate's `docker-compose-dev.yml` and the `REPLICA_SET_*` variables of its `example.env`. A replica set is required (pvServer uses change streams), but one node is enough by the source: `mongoSetup/replSetup.py` takes `REPLICA_SET_MEMBERS=localhost:27017`. One node is not tested here. Ports 27017 (to 27019 for three nodes) |
| `initializeadmindb`, `adminDbInit/`, `users/` | login, users, access rights | See "Login" below |
| `alarmhandlerserver`, `initializealarmhandlerdb`, `alarmHandlerDbInit/` | RAS alarm handler pages | MongoDB, both services from the boilerplate, and our own `alarmHandlerDbInit/initDBData/pvList.json` with MIST-2 PVs (the boilerplate's lists demo PVs) |
| `initializeloadsavedb`, `loadSaveDbInit/` | load/save of settings | MongoDB, the service and a `loadSaveDbInit/systems/<system>/` with our PVs |
| `signalcli`, `signalcli/` | Signal notifications of the alarm handler | The service and a registered Signal number. Only useful with the alarm handler |
| `storybook`, `stagingunsecurestylguidepvserver`, `ReactApp/.storybook/`, `styleguide.config.js`, `test-runner-jest.config.cjs`, `docker/storybook*`, `docker/testRunner` | RAS style guide (component documentation) on port 6060 | The services from the boilerplate and the files above. The submodule has the component docs as `*.md` next to each component, readable without it |
| `stagingdemoioc`, `stagingtestioc`, `areadetectorsim`, `epics/`, `docker/demoioc`, `docker/stagingioc` | demo IOCs for the demo pages | not needed: our IOCs are in `emulation/` |
| `ReactApp/src/components/` (demos, staging examples, `customComponents` examples), `AppMain.jsx`, `docs/`, `reportWebVitals.js`, `serviceWorker.js`, `public/Harp.gltf`, `ReactApp/img/` | demo pages and their documentation | not needed. Our own components go to `ReactApp/src/components/` |
| `docker/frontend` (production build of the client), `docker-compose.yml`, `docker-compose-prod-with-demoioc.yml` | production deployment | When the GUI goes to the lab: the boilerplate's `docker-compose.yml` with its `frontend` service and `nginx.production.conf`, HTTPS certificates in `certificates/` |
| `certificates/` | HTTPS (`SECURE=true`) | needed for login in production, see below |
| `docs/` (migration notes V4 to V8), `README.md`, `_config.yml` | upstream documentation | read them in the boilerplate repository |

### Login

Login is off (`VITE_EnableLogin=false` in `.env`): every browser gets read and
write access to every PV. Enabling it involves:

1. MongoDB (above) and the `initializeadmindb` service, which seeds users and
   access rules from `adminDbInit/config/users.json` and `pvAccess.json`
   (copy them from the boilerplate; the default user is admin/admin, change it).
2. `VITE_EnableLogin=true` and a secret `SECRET_PWD_KEY` in `.env` (without
   it pvServer uses a built-in key, so tokens could be forged).
3. A `/Login` route in `ReactApp/src/AppRoutes.jsx`:
   `<Route path="/Login" element={<Login version="V8.1.0" timeout={5000} />} />`
   with `Login` from `React-Automation-Studio/components/SystemComponents/Login`.
   The pages are already wrapped in `ProtectedRoute`.
4. RAS recommends HTTPS with login (`SECURE=true`, certificates, the
   `nginx.httpredirect.conf`), because the tokens travel in clear text otherwise.

## Updating to a later RAS release

1. Read the release notes and the migration note in the boilerplate
   (`docs/migrate-from-V8-to-V9.md` or similar).
2. Move the submodule:
   ```
   cd RAS/mist2/submodules/React-Automation-Studio
   git fetch --tags && git checkout <new tag>
   cd - && git add RAS/mist2/submodules/React-Automation-Studio
   ```
3. Compare the boilerplate at the matching commit with the files listed under
   "What was kept" and carry over its changes, in particular
   `ReactApp/package.json` (dependency versions must match the RAS sources),
   `vite.config.js` and the four Dockerfiles. Compare
   `submodules/React-Automation-Studio/nginx/nginx.dev.conf` with
   `nginx/mist2.dev.conf.template`.
4. Update the commit and tag in the table at the top of this file.
5. `make build`, `make dev-up`, `tools/pv-proof.sh 172.31.0 --with-standin-iocs`.
