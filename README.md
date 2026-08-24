# Smart Home over KNX + ThingsBoard IoT Gateway

> Simulating a KNX smart home with **KNX Virtual**, bridging it to **ThingsBoard** through the **ThingsBoard IoT Gateway (KNX Connector)**, and controlling & monitoring it in real time from a **web dashboard** and the **mobile app** — both directions.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![KNX](https://img.shields.io/badge/KNX-Virtual-blue)
![ThingsBoard](https://img.shields.io/badge/ThingsBoard-CE-orange)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)
![xknx](https://img.shields.io/badge/xknx-3.16.0-informational)

🇮🇷 **نسخه فارسی این مستند:** [README.fa.md](README.fa.md)

Final project for the **Internet of Things (IoT)** course — Shahid Beheshti University, Spring 2025–26 (1404–1405). Instructor: **Dr. Attarzadeh**.

---

## Table of contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [KNX devices & topology](#knx-devices--topology)
5. [Group address map](#group-address-map)
6. [HVAC / setpoint chain](#hvac--setpoint-chain)
7. [Environment & network](#environment--network)
8. [Getting started](#getting-started)
9. [Dashboard & widgets](#dashboard--widgets)
10. [Mobile access](#mobile-access)
11. [Challenges & solutions](#challenges--solutions)
12. [Troubleshooting](#troubleshooting)
13. [Screenshots](#screenshots)
14. [Repository structure](#repository-structure)
15. [Security note](#security-note)
16. [Author](#author)
17. [License](#license)

---

## Overview

The goal of this project is to build a complete IoT loop for a smart home:

- **Read (KNX → ThingsBoard):** room temperature, blind position, light/valve state, effective setpoint.
- **Write (ThingsBoard → KNX):** light on/off, blind up/down/stop, HVAC mode (Comfort/Standby), and thermostat setpoint.

The simulated KNX bus (KNX Virtual) is connected to ThingsBoard CE via the ThingsBoard IoT Gateway using the `xknx` library, and the whole system is controlled from the web and the mobile app.

## Architecture

```text
KNX Virtual
   ⇅  KNXnet/IP Tunneling (UDP 3671)
ThingsBoard IoT Gateway  (KNX Connector / xknx)
   ⇅  MQTT (1883)
ThingsBoard CE (Docker)
   ⇅  HTTP (8080)
Web dashboard  +  ThingsBoard mobile app
```

- **KNX Virtual** runs on the Windows host and simulates the KNX bus (light, blinds, heating controller, etc.). It exposes a single KNXnet/IP tunnel over UDP only.
- **ThingsBoard IoT Gateway** runs in Docker on an Ubuntu VM (VMware) and speaks KNX through `xknx`: it reads (uplink) and writes (downlink).
- **ThingsBoard CE** runs in Docker on the same VM, hosts the `Living Room` device, dashboards, and the Rule Engine.
- The user controls/monitors from a **web browser** and the **ThingsBoard mobile app**.

## Features

- 💡 Light on/off (switch)
- 🪟 Blinds up / stop / down + live position (%)
- 🌡️ Live room & outside temperature telemetry
- 🎛️ Thermostat setpoint write + effective/actual setpoint feedback
- ❄️🔥 HVAC mode switching (Comfort / Standby)
- 📱 Two-way, real-time control from web **and** mobile
- 🧩 Custom 3-button blind widget (imported as a widget type)
- 🔧 Patched KNX connector for DPT 275.100 (4-mode setpoint) and DPT 20.102 (HVAC mode)

## KNX devices & topology

| Physical address | Device | Role |
|---|---|---|
| 1.1.1 | D7 — Switch Actuator (SA) | Light on/off |
| 1.1.2 | D2 — Blinds (BS) | Blinds |
| 1.1.3 | D4 — KliX (HMI) | Thermostat / temperature display |
| 1.1.4 | D15 — Setpoint Manager (RTSM) | Computes effective setpoint |
| 1.1.5 | D16 — Heat Controller (HC) | Actual setpoint + valve command |
| 1.1.6 | D17 — Heat Exchanger (HE) | Heating/cooling simulation |
| — | D6 — Valve Actuator (VA) | Heating valve |
| 1.1.8 | WM — Weather Module | Outside temperature |
| 1.0.255 | Tunnel | Gateway individual address |
| 1.1.255 | KNX Virtual IF | Interface individual address |

Project type in KNX Virtual: **Basic Functions – single room**.

## Group address map

Structure: `1=Lighting, 2=Blinds, 3=Temperature, 4=HVAC`.

| Device | Object | Group Address | DPT | Direction |
|---|---|---|---|---|
| 1.1.1 SA | Light Switch | `1/1/1` | 1.001 | write |
| 1.1.2 BS | Blind Move | `2/1/1` | 1.008 | write |
| 1.1.2 BS | Blind Step/Stop | `2/1/2` | 1.007 | write |
| 1.1.2 BS | Blind Position | `2/1/3` | 5.001 % | read |
| 1.1.3 KX | Current Temp (room) | `3/1/2` | 9.001 °C | read |
| 1.1.3 KX | HVAC Mode-User | `4/1/1` | 20.102 | write |
| 1.1.3 KX | Setpoint Cool-User | `4/1/3` | 275.100 | HMI sends |
| 1.1.4 SP | Setpoint Heat-User | `4/1/2` | 275.100 | write |
| 1.1.4 SP | Setpoint Heat-Effective | `4/2/2` | 9.001 °C | SP output |
| 1.1.5 HC | Setpoint-Actual | `4/3/3` | 9.001 °C | read / feedback |
| 1.1.5 HC | Valve Heat | `4/4/2` | 5.001 % | write |
| 1.1.5 HC | Valve Cool | `4/4/3` | 5.001 % | — |
| 1.1.8 WM | Outside Temperature | `4/0/1` | 9.001 °C | read |

## HVAC / setpoint chain

```text
KliX (HMI/D4) --User setpoint--> Setpoint Manager (SP/D15) --Effective--> Heat Controller (HC/D16) --Valve--> Valve Actuator
     ^                                                                                                       |
     └------------------------------- Actual setpoint (feedback) <-----------------------------------------┘
```

**Key lesson:** writing to `4/2/2` (Effective) has no effect — the setpoint manager overwrites it. You must write to the **User setpoint** (`4/1/2`, DPT 275.100), exactly like the KliX/HMI does. The connector was patched to encode this DPT (see [`config/patches/knx_connector_dpt.py`](config/patches/knx_connector_dpt.py)).

## Environment & network

| Item | Value |
|---|---|
| Host OS | Windows |
| VM | Ubuntu 24.04 on VMware |
| Host IP on VMnet8 (NAT) | `192.168.131.1` |
| VM IP (NAT) | `192.168.131.129` (variable — check with `ip -4 addr`) |
| KNX Virtual | UDP `0.0.0.0:3671` on the Windows host |
| ThingsBoard + Gateway | Docker on the same VM |
| ThingsBoard web | `http://<VM-IP>:8080` |

> **Most important networking point:** because both the VM and the Windows host are on the NAT subnet `192.168.131.0/24`, the connector must point to the Windows VMnet8 IP (`192.168.131.1`). The VM's own IP can change on every restart.

On Windows, `KNX Virtual` reads its interface from:
`C:\ProgramData\KNX\KV\v26\interface.txt` (one line: `192.168.131.1:3671`). After editing it, fully close and reopen KNX Virtual.

## Getting started

### 1. KNX side (Windows)

1. Install **KNX Virtual** and **ETS**.
2. Load the ETS project from [`hardware/IOT_Finale.knxproj`](hardware/IOT_Finale.knxproj).
3. Make sure KNX Virtual is listening on UDP `3671` and the interface points to the host VMnet8 IP.

### 2. ThingsBoard + Gateway (Docker on the VM)

| Container | Notes | Ports |
|---|---|---|
| `thingsboard-setup-mytb-1` | ThingsBoard CE + internal Postgres | 8080 (web), 1883 (MQTT) |
| `tb-gateway` (v3.7.8) | IoT Gateway, `network_mode: host` | — |

Gateway `docker-compose.yml` essentials:

```yaml
environment:
  - host=127.0.0.1          # gateway and broker are on the same VM
  - port=1883
  - accessToken=YOUR_DEVICE_ACCESS_TOKEN   # do NOT commit the real token
network_mode: host
```

Common commands:

```bash
cd ~/tb-gateway
docker compose up -d          # after an env change
docker compose restart        # quick restart
docker compose logs -f --tail=50
```

> ⚠️ Never run `docker compose down` — it resets the `xknx` pins and the file patches. Use `stop/start/restart` only.

### 3. KNX Connector

Path in the UI: `Gateways → KNX Gateway → Connectors → KNX → Configuration`.

The target config is in [`config/knx.json`](config/knx.json). Three mapping sections:

- **`timeseries`** = reading from KNX (monitoring; needs the KNX `R` flag).
- **`attributeUpdates`** = writing to KNX on a shared-attribute change (needs the `W` flag).
- **`serverSideRpc`** = read/write via RPC (`setState`, `setSetpoint`).

Apply a connector code patch:

```bash
docker cp tb-gateway:/thingsboard_gateway/connectors/knx/knx_connector.py ~/knx_connector.py.bak
docker cp ~/knx_connector.py tb-gateway:/thingsboard_gateway/connectors/knx/knx_connector.py
docker restart tb-gateway
```

## Dashboard & widgets

The **Smart Home** dashboard includes:

| Capability | Widget | Mechanism |
|---|---|---|
| Light on/off | Power button | Set attribute `light` (Boolean) or RPC `setState` |
| HVAC mode (Comfort/Standby) | Single Switch | RPC `set` with `groupAddress=4/1/1; dataType=hvac_mode; value=2` (Standby) / `value=1` (Comfort) |
| Blinds up/stop/down | Custom 3-button widget | Set shared attributes: `blindMove=false` (Up), `blindStop=true` (Stop), `blindMove=true` (Down) |
| Blind position | Value card | shows `blindPosition` (%) |
| Setpoint / thermostat | Gauge + input | `targetSetpoint` (write) + `setpointDisplay` + `roomTemp` (read) |

> The 3-button blind control must be built as a **custom widget type** and imported from `Widgets Library → Import`, not from the dashboard import. It writes via `attributeService.saveEntityAttributes(...)` on `SHARED_SCOPE`.

## Mobile access

Because ThingsBoard runs on a NAT'd VM (`192.168.131.129:8080`) and the phone is on the Windows Wi-Fi/LAN, a **port mapping** on the Windows host bridges the two:

```bat
netsh interface portproxy add v4tov4 listenport=8080 listenaddress=0.0.0.0 connectport=8080 connectaddress=192.168.131.129
netsh advfirewall firewall add rule name="Allow ThingsBoard 8080" dir=in action=allow protocol=TCP localport=8080
```

Then browse from the phone (same Wi-Fi) to `http://<windows-lan-ip>:8080`. If the VM IP changes after a restart, update `connectaddress`. To remove the mapping:

```bat
netsh interface portproxy delete v4tov4 listenport=8080 listenaddress=0.0.0.0
```

## Challenges & solutions

- **Hard-coded VM IP** — an old VM IP was hard-coded in two places; symptoms were `[Errno 99] Cannot assign requested address` and the gateway never connecting. Fix: set `localIp` to the current VM IP and `host=127.0.0.1` in compose.
- **Lost write telegrams** — `xknx.tools.group_value_write` is synchronous fire-and-forget (no retry). During brief tunnel drops, writes were lost while awaited+retried reads survived.
- **Wrong setpoint target** — writing the Effective setpoint (`4/2/2`) does nothing; write the User setpoint (`4/1/2`, DPT 275.100) instead. Fixed via the connector patch.
- **Single-tunnel limitation (root cause)** — KNX Virtual exposes only one KNXnet/IP tunnel. If ETS Group Monitor and the gateway both grab it, they fight over the tunnel (~30s connect/lost cycle), and each reconnect resets KNX Virtual to its default (`comfort=22`). Fix: keep ETS disconnected and let only the gateway hold the tunnel.
- **Uplink converter bug** — `knx_uplink_converter.py ... 'NoneType' object is not subscriptable`. Suggested patch: `if hasattr(converted_value, 'value'): converted_value = converted_value.value`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `[Errno 99] Cannot assign requested address` | `localIp` points to a non-existent VM IP | Set `localIp` to current `ip -4 addr` |
| Any UI change has no effect, same error | wrong `host` | `host=127.0.0.1` in compose, then rebuild |
| `No usable KNX/IP device found` | wrong discovery/gateway IP | `type: TUNNELING` with `gatewayIp: 192.168.131.1` |
| `Living Room = Inactive` | no successful read yet | keep at least one readable `timeseries` |
| Setpoint/mode won't stick | ETS + gateway share one tunnel | disconnect ETS; gateway-only on the tunnel |
| `database error` at login | Postgres not up yet | wait, or `docker restart thingsboard-setup-mytb-1` |
| Phone can't reach the server | no NAT port mapping | `netsh portproxy` + open the firewall port |

## Screenshots

### ThingsBoard — Smart Home dashboard
![ThingsBoard Smart Home dashboard](docs/images/thingsboard-dashboard.jpg)

### ThingsBoard — devices
![ThingsBoard devices](docs/images/thingsboard-devices.jpg)

### KNX Virtual — device panel
![KNX Virtual panel](docs/images/knx-virtual-panel.jpg)

### ETS — topology
![ETS topology](docs/images/ets-topology.jpg)

### ETS — device list
![ETS device list](docs/images/ets-device-list.jpg)

### ETS — group objects (KliX / HMI)
![ETS KliX group objects](docs/images/ets-klix-group-objects.jpg)

### ETS — group objects (Heat Controller)
![ETS Heat Controller group objects](docs/images/ets-hc-group-objects.jpg)

### ETS — group objects (Blinds)
![ETS Blinds group objects](docs/images/ets-blinds-group-objects.jpg)

### ETS — group object (Switch Actuator)
![ETS Switch Actuator group object](docs/images/ets-switch-group-object.jpg)

## Repository structure

```text
.
├─ README.md                     # English documentation (this file)
├─ README.fa.md                  # Persian documentation
├─ LICENSE                       # MIT license
├─ .gitignore
├─ config/
│  ├─ knx.json                   # KNX Connector configuration (token redacted)
│  └─ patches/
│     └─ knx_connector_dpt.py    # DPT 275.100 / 20.102 connector patch
├─ hardware/
│  └─ IOT_Finale.knxproj         # ETS project file
└─ docs/
   ├─ IOT_final_Report.pdf       # Full project report (Persian)
   ├─ Project_Brief.pdf          # Course assignment brief (Persian)
   └─ images/                    # Screenshots used in the docs
```

## Security note

The real ThingsBoard device access token and default `tenant@thingsboard.org` credentials from the report are **intentionally not published** in this repository. Replace `YOUR_DEVICE_ACCESS_TOKEN` and `REPLACE-WITH-YOUR-CONNECTOR-ID` in [`config/knx.json`](config/knx.json) and your compose file with your own values, and keep secrets out of version control (see `.gitignore`).

## Author

**Mohsen Norouzi (محسن نوروزی)**

- GitHub: [@mohsen-norouzi237](https://github.com/mohsen-norouzi237)
- Email: [mnorouzi2018@gmail.com](mailto:mnorouzi2018@gmail.com)
- LinkedIn: [mohsen-norouzi](https://www.linkedin.com/in/mohsen-norouzi-143bb5336/)

## License

Released under the [MIT License](LICENSE).

---

*Reference: ThingsBoard KNX connector — https://thingsboard.io/docs/iot-gateway/config/knx/ (xknx v3.16.0 / gateway v3.7.8).*
