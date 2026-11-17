# CSV Import Templates

**Audience:** client admins preparing data, and developers building the import endpoints
**Status:** Draft v1 — 2026-11-17
**Files:** [import-templates/](import-templates/)
**Related:** [API.md](API.md) · [DEPLOYMENT_REQUIREMENTS.md](DEPLOYMENT_REQUIREMENTS.md) §4

---

## 1. General rules (all files)

| Rule | Detail |
|---|---|
| Encoding | UTF-8 (required for Bangla names). In Excel use *Save As → CSV UTF-8* |
| Separator | Comma. Wrap a value in double quotes if it contains a comma |
| Header row | Required, exactly as in the template; column order does not matter |
| Dates | `YYYY-MM-DD` |
| Date-times | `YYYY-MM-DD HH:MM` in **factory local time**; the server converts to UTC using the factory time zone |
| Empty values | Leave the cell empty; optional columns are marked "no" below |
| Matching | Rows match existing records by their code (`station_code`, `asset_code`, `employee_code`, …). Existing → updated; new → created |
| Unknown list values | A machine type, brand or similar list value that does not exist yet is rejected, unless the import is run with **"Create missing list values"** ticked |
| Size | Up to 10,000 rows per file |

### Import behaviour
1. Upload → the server validates **every row** first.
2. A preview shows: rows to create, rows to update, rows with errors (row number + column + reason).
3. The admin chooses **Import valid rows** or **Cancel**. Nothing is written before this step.
4. The result and the original file are stored and recorded in the audit log.

## 2. Templates

### 2.1 `org_structure.csv` → `POST /org/import`
Creates floors, lines and stations. One row per station; floor and line columns repeat.

| Column | Required | Notes |
|---|---|---|
| `factory_code` | yes | Factory must already exist |
| `floor_code` | yes | |
| `floor_name` | yes | |
| `line_code` | yes | Unique inside the floor |
| `line_name` | yes | |
| `station_code` | yes | Unique in the install, e.g. `L1-S001` |
| `station_name` | no | Defaults to the code |

Tip: for many identical stations, use **Bulk create stations** in the UI instead (`POST /stations/bulk`).

### 2.2 `machines.csv` → `POST /machines/import`
| Column | Required | Notes |
|---|---|---|
| `asset_code` | yes | Factory's own machine ID |
| `factory_code` | yes | |
| `machine_type` | yes | Must match a machine type list value (e.g. Lockstitch, Overlock, Flatlock) |
| `brand` | yes | Any brand; must match a brand list value |
| `model` | no | |
| `serial` | no | |
| `station_code` | no | If given, the machine is placed on this station from import time |
| `status` | no | `active` (default), `maintenance`, `inactive` |

### 2.3 `workers.csv` → `POST /workers/import`
| Column | Required | Notes |
|---|---|---|
| `employee_code` | yes | Factory employee ID |
| `factory_code` | yes | |
| `full_name` | yes | English |
| `full_name_bn` | no | Bangla |
| `rfid_card_id` | no | Same number as the attendance card, if the factory uses cards |
| `joined_on` | no | `YYYY-MM-DD` |
| `skills` | no | `operation_code:level` separated by `;`, level 1–5. Example: `OP-SLV-01:4;OP-COL-02:2` |

### 2.4 `operations.csv` → `POST /operations/import`
| Column | Required | Notes |
|---|---|---|
| `product_code` | yes | Product created if new |
| `product_name` | yes | |
| `style_no` | no | |
| `operation_code` | yes | |
| `operation_name` | yes | English |
| `operation_name_bn` | no | Bangla |
| `smv` | yes | Standard Minute Value, minutes, up to 3 decimals |
| `machine_type` | yes | Machine type list value |
| `count_unit` | yes | Plain-language definition of one unit, e.g. "One sleeve attached" |
| `difficulty_group` | no | Groups operations for fair ranking (e.g. A, B, C) |

### 2.5 `needle_batches.csv` → `POST /needle-batches/import`
| Column | Required | Notes |
|---|---|---|
| `supplier_name` | yes | Supplier created if new |
| `brand` | yes | Needle brand |
| `system` | yes | e.g. DBx1, DCx27 |
| `size_nm` | yes | Metric size, e.g. 90 |
| `point_type` | no | e.g. SES, FFG |
| `lot_no` | yes | Unique per supplier |
| `received_on` | yes | `YYYY-MM-DD` |
| `qty_received` | yes | Whole number |

### 2.6 `production_entries.csv` → `POST /production-entries/import`
For factories that keep production counts in another system or spreadsheet.

| Column | Required | Notes |
|---|---|---|
| `employee_code` | yes | |
| `station_code` | yes | |
| `operation_code` | yes | |
| `period_start` | yes | Factory local time |
| `period_end` | yes | After `period_start` |
| `qty_accepted` | yes | |
| `qty_rework` | no | Default 0 |
| `qty_rejected` | no | Default 0 |

Imported entries arrive as `draft`; a supervisor confirms them (or the import is run with **"Mark as confirmed"**).

### 2.7 `attendance.csv` → `POST /attendance/import`
Card punches exported from the factory's existing attendance system.

| Column | Required | Notes |
|---|---|---|
| `employee_code` | one of the two | Either the employee code or the card ID must be filled |
| `card_id` | one of the two | Matched against `workers.rfid_card_id` |
| `punch_time` | yes | Factory local time |
| `direction` | no | `in`, `out` or empty |
| `device` | no | Gate / reader name |

Punches are stored as `rfid_tap` events with `source = import` and are used to confirm worker presence. They do not create station assignments.
