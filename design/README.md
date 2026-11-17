# StitchSense design (review)

Design canvas export, 2026-11-17.

## Files

| File | Screen |
|---|---|
| `Main.dc.html` | Public landing page |
| `Overview.dc.html` | Admin overview + alert center |
| `Floor.dc.html` | Supervisor live floor, review queue, station timeline, hourly output entry |
| `Needles.dc.html` | Needle lots + investigation, performance ranking + score explanation |
| `canvas.json` | Canvas layout (artboard positions, notes) |

The `.dc.html` files are design-canvas components. They render only inside the canvas viewer (they load its `support.js` runtime and use `{{…}}` templates and `<sc-for>` loops), so opening them directly in a browser shows unrendered markup. Treat them as the visual spec when building `apps/web`. To change the design, edit it on the canvas and import again.

All numbers and worker names are sample data.

## Design tokens ("Floor ledger")

| Token | Light | Use |
|---|---|---|
| `--bg` | `#F4F2ED` | Page ground |
| `--surface` | `#FFFFFF` | Panels, tables |
| `--sunk` | `#ECE9E2` | Bar tracks, read-only fields |
| `--ink` | `#17191C` | Text |
| `--ink2` | `#4A4F57` | Secondary text (passes 4.5:1 on white) |
| `--line` / `--line2` | `#DEDAD1` / `#C9C4B8` | Hairlines / control borders |
| `--brand` | `#1E4FD8` (hover `#163BA6`) | Actions, data, links, focus ring |
| `--run` | `#1E7B4F` | Machine running |
| `--idle` | `#9A5806` on `#FBEFD9` | Idle / warning |
| `--down` | `#B42318` on `#FBE3E0` | Machine down / critical |
| `--off` | `#6B7078` on `#E7E6E2`, dashed | No data / offline |

Rules: a state never relies on colour alone (shape mark ▲ ✕ ?, label or dashed border too); one accent (blue); no gradients, glows or thick coloured side bars; 44px touch targets on supervisor screens.

Type: IBM Plex Sans Condensed (display), IBM Plex Sans (UI), IBM Plex Mono (codes and numbers only, tabular), Noto Sans Bengali (Bangla).
