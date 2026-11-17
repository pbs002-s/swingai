# Deployment Requirements (per client factory)

**Audience:** client factory management / IT, and our installation team
**Status:** Draft v1 — 2026-11-17
**Related:** [PRD](PRD.md) · [TRD](TRD.md)

Each client runs its own installation on its own hardware or its own cloud account. This document lists everything a client needs before installation and go-live.

> Prices are rough USD estimates (late 2026) for budgeting only. Get local quotes. Edge stream capacity must be confirmed by a benchmark on the chosen hardware before ordering at scale.

---

## 1. What runs where

| Tier | Location | Runs |
|---|---|---|
| Station devices | On each sewing station | Machine sensor (ESP32 + current clamp), optional RFID reader, camera |
| Edge box | Factory floor network room (1 per floor or per ~12–16 camera streams) | MQTT broker, vision service, edge collector with offline buffer |
| Central server | Client server room **or** client-owned cloud VPS | Web app, API, database, background jobs, file storage |

Small installs (≤ 20 stations) can run the central stack on the same machine as the edge box.

## 2. Hardware

### 2.1 Per station
| Item | Purpose | Spec | Approx. cost | Release |
|---|---|---|---|---|
| Machine sensor | Running / stopped, operating hours | ESP32 + SCT-013 split-core current transformer (clamps on the motor supply wire; non-invasive) + enclosure + 5 V supply | $12–20 | R2 |
| RFID reader (optional) | Worker check-in at station | 13.56 MHz (PN532 / RC522) wired to the same ESP32 | $5–8 + $0.30/card | R2 |
| Activity camera | Worker activity, phone use | 2–4 MP PoE IP camera, RTSP, H.264/H.265, wide angle; mounted overhead/angled; 1 camera can cover 1–2 stations depending on layout | $40–80 | R3 |
| Seam inspection camera (selected stations only) | Skipped-stitch inspection | Industrial USB3/GigE camera, macro lens, LED ring light, fixed mount after the needle | $250–600 | R4 |

The current clamp must be installed by a **qualified electrician**, around a single conductor (not the whole cable), with the machine powered off.

### 2.2 Edge box (per ~12–16 camera streams at 5 fps)
| Option | Spec | Approx. cost |
|---|---|---|
| A. NVIDIA Jetson Orin NX 16 GB dev kit / carrier | 8–12 streams (estimate), low power, fanless options | $700–1,000 |
| B. Mini PC / small tower with GPU | 8-core CPU, 32 GB RAM, RTX 4060 8 GB, 1 TB NVMe; ~16–24 streams (estimate) | $1,000–1,400 |
| R1–R2 only (no vision) | Any small PC or Raspberry Pi 5 (8 GB) with SSD — runs MQTT + collector only | $120–300 |

Add a UPS (≥ 30 min) for every edge box.

### 2.3 Network
| Item | Requirement |
|---|---|
| Cabling | Cat6 to every camera; cameras on PoE |
| Switches | PoE+ managed switch, 1 port per camera + uplink; budget ≥ 15 W per camera |
| VLANs | Separate VLAN for cameras/sensors; cameras have no internet access |
| Wi-Fi | 2.4 GHz coverage at every station for ESP32 sensors (or wired Ethernet ESP32 variant) |
| Edge ↔ central | LAN if central is on-prem; if central is in the cloud, ≥ 10 Mbps stable internet (events use < 1 Mbps; evidence uploads are small) |
| Time sync | NTP reachable from edge boxes (or a local NTP server) |
| Power | UPS for edge box, PoE switch and on-prem server |

### 2.4 Central server
| Size | Stations | On-prem spec | Cloud VPS spec | Approx. cloud cost |
|---|---|---|---|---|
| Small | ≤ 50 | 4 cores, 16 GB RAM, 500 GB SSD | 4 vCPU, 8–16 GB, 160 GB SSD | $25–50 / month |
| Medium | ≤ 200 | 8 cores, 32 GB RAM, 1 TB NVMe (RAID 1) | 8 vCPU, 16–32 GB, 320 GB SSD + object storage | $60–120 / month |
| Large | ≤ 500 | 16 cores, 64 GB RAM, 2 TB NVMe (RAID 1) | 16 vCPU, 64 GB, managed Postgres optional | $150–300 / month |

Storage estimate (200 stations): events ≈ 5 GB / month including indexes; evidence images ≈ 3 GB rolling with 30-day retention; reports and backups extra.

## 3. Software requirements

| Item | Requirement |
|---|---|
| OS | Ubuntu Server 24.04 LTS (central and x86 edge); JetPack 6 on Jetson |
| Runtime | Docker Engine + Docker Compose plugin; NVIDIA Container Toolkit on GPU edge |
| Database | PostgreSQL 16 (bundled container by default; client-managed Postgres supported) |
| Other services | Redis 7, MinIO, Caddy (all bundled as containers) |
| Domain / TLS | A domain or subdomain pointing to the central server (cloud), **or** an internal hostname with a client-trusted certificate (on-prem) |
| Email (optional) | SMTP account for alert emails and password resets |
| Backup target | Off-site storage (second server, NAS, or S3-compatible bucket) for nightly DB + file backups |
| Client browsers | Latest Chrome / Edge / Firefox on PC or tablet (10"+ for supervisors) |

## 4. Data the client must provide before setup

1. Factory structure: floors, lines, stations (codes and names).
2. Machine list: asset code, type, brand, model, serial, current station.
3. Worker list: employee code, name (English and Bangla), RFID card numbers if used.
4. Products / operations with **SMV** and the counting-unit definition per operation.
5. Shift, break, overtime and weekly-limit policies; holiday calendar.
6. Production targets per operation / line / shift.
7. Needle suppliers, models and current batch / lot records.
8. Defect types and current quality inspection practice.
9. Current bonus and training rules (if they want those features).
10. Users who need access, and their roles.

CSV templates for items 1–3 and 7 will be provided.

## 5. People needed at the client

| Role | Responsibility |
|---|---|
| Project owner (management) | Approves policies, privacy notice, go-live |
| IT contact | Network, VLAN, server / cloud account, backups |
| Electrician / machine technician | Sensor installation, machine signal checks |
| Line supervisor(s) — pilot champions | Daily review queue, manual production entry, feedback |
| HR / compliance | Worker notice, consent and retention policy |

## 6. Legal and privacy prerequisites

- Written notice to workers: what is monitored, why, where cameras point, how long data is kept, how to dispute an event.
- Compliance check against local labour and data-protection law (client's responsibility, with our documentation support).
- Signed data-processing agreement if our team has remote access for support.
- Camera zones restricted to the work area; no cameras in break rooms, prayer rooms or toilets.
- Retention settings agreed (defaults: evidence 30 days, events 2 years).

## 7. Example pilot bill of materials (10 stations, all releases)

| Item | Qty | Unit (USD) | Total (USD) |
|---|---|---|---|
| Machine sensor kit (ESP32 + CT clamp + enclosure + PSU) | 10 | 18 | 180 |
| RFID reader + 30 cards | 10 + 30 | 7 / 0.30 | 79 |
| PoE IP camera (1 per station for the pilot) | 10 | 60 | 600 |
| Seam inspection camera kit | 2 | 400 | 800 |
| Edge box (option B, GPU mini PC) | 1 | 1,200 | 1,200 |
| 16-port PoE+ managed switch | 1 | 250 | 250 |
| UPS (edge + switch) | 1 | 150 | 150 |
| Cabling, mounts, installation materials | lot | — | 300 |
| **Hardware total** | | | **≈ 3,560** |
| Central server | Cloud VPS small | — | ≈ 40 / month |

An R1–R2-only pilot (no cameras) costs roughly $600–900 in hardware.

## 8. Installation checklist

- [ ] Site survey done (machines, layout, lighting, network, power)
- [ ] Hardware delivered and network/VLAN ready
- [ ] Central server provisioned; DNS + TLS working
- [ ] `docker compose up` on central; health check green
- [ ] Admin account created; factory time zone set
- [ ] Master data imported (stations, machines, workers, operations/SMV)
- [ ] Policies created (shift, break, targets, thresholds)
- [ ] Edge box installed; devices registered; tokens issued
- [ ] Sensors installed and verified against observed machine running/stopped
- [ ] Cameras mounted; zones drawn; test events visible
- [ ] Backups configured and **one restore tested**
- [ ] Worker notice issued; privacy sign-off received
- [ ] Supervisors trained (review queue, production entry, reason codes)
- [ ] Observation mode started; acceptance criteria agreed (PRD §8)
