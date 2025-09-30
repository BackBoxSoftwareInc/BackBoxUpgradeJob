# BackBox Device OS Upgrade (Customer Demo)

A reference automation showing how to:
- Authenticate to BackBox
- Resolve devices by external ID (from a CSV or 3rd‑party export)
- Add those devices to an existing upgrade job
- Upload an upgrade artifact (e.g., `upgrade.zip`) and set it in a dynamic field via the new API

Use this to demonstrate BackBox extensibility and API-driven upgrade workflows.

---
## Architecture Overview
| Component | Purpose |
|-----------|---------|
| `BackBoxDeviceOSUpgrade.py` | Core script (Python 3.12+), idempotent and environment-driven |
| `BackBox_OS_Upgrade_Demo.ipynb` | Optional interactive walkthrough for demos |
| `Devices_To_Upgrade.csv` | External IDs (1 per line; header optional) |
| `upgrade.zip` / `upgradefile.tgz` | Example upgrade artifact to upload |
| `.env` | Secure, local configuration (not committed) |

---
## Prerequisites
1. BackBox 7.x environment (access + API reachability)
2. Devices added in BackBox with their External ID values set to match each line in `Devices_To_Upgrade.csv`
3. A Task Job that utilizes the `Cisco -> IOS -> SCP -> Upgrade` automation. To use the default values in the script name this job exactly `UpgradeJob` (or change `JOB_TO_EXECUTE` in `.env`)
4. Python 3.12 (recommended) + pip
5. Network access from your workstation to BackBox HTTPS port

---
## Quick Start (CLI)
```bash
# 1. Create & activate a virtual environment (Windows PowerShell example)
python -m venv .venv
./.venv/Scripts/Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env (see template below) and place upgrade file (e.g., upgrade.zip)

# 4. Run
python BackBoxDeviceOSUpgrade.py
```
Exit code 0 = success. Non‑zero codes map to failure phases (see [Exit Codes](#exit-codes)).

---
## .env Example
```
BACKBOX_IP=your.backbox.host
BACKBOX_USER=your_user
BACKBOX_PASSWORD=your_password
JOB_TO_EXECUTE=UpgradeJob
JOB_FILE_NAME=upgrade.zip
DEVICES_FILE=./Devices_To_Upgrade.csv
DYNAMIC_FIELD_NAME=IOS bin File
# Optional overrides
# DYNAMIC_FIELD_ID=123            # Force a specific dynamic field id
# VERIFY_SSL=true                 # Enable certificate validation
# LOG_LEVEL=DEBUG                 # More verbose logging
```
> Provide a sanitized `.env.example` to customers—never commit credentials.

---
## CSV Format
Minimal format (header optional):
```
External_ID
FD1345
```
Script de-duplicates and skips blank lines.

---
## Notebook Demo (Optional)
Open the notebook for a step-by-step run:
```bash
jupyter notebook BackBox_OS_Upgrade_Demo.ipynb
```
Follow top-to-bottom cells: dependencies → config check → helper functions → run orchestrator → inspect dynamic fields.

Use `inspect_dynamic_fields(CFG, <job_id>)` (last cell) to show dynamic field IDs/UI names live during the demo.

---
## Dynamic Field Handling
The script:
1. Fetches job dynamic fields via `PUT tasks/jobs/getTaskJobDynamicFields/{jobID}`
2. Locates the field by `uiName` (default: `IOS bin File` or overridden via `DYNAMIC_FIELD_NAME`)
3. Attempts candidate ID values (including negative internal IDs) unless `DYNAMIC_FIELD_ID` is set
4. Issues a `PUT tasks/jobs/updateTaskJobDynamicFields` with the chosen ID

If all attempts fail, it logs each attempt and exits with code 12.

---
## Exit Codes
| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Missing required environment variables |
| 3 | Authentication failure |
| 4 | Upgrade file not found |
| 5 | File upload failure / invalid response |
| 6 | Could not list jobs |
| 7 | Specified job not found |
| 8 | Fetch job details failed |
| 9 | Failed to add devices to job |
| 10 | Dynamic fields fetch failed |
| 11 | Dynamic field not found by name |
| 12 | All dynamic field update attempts failed |

---
## Troubleshooting
| Symptom | Likely Cause | Action |
|---------|--------------|--------|
| Login failed (code 3) | Wrong credentials / IP / SSL trust | Verify `.env`, test URL in browser |
| No device IDs resolved | External IDs mismatch | Confirm BackBox External ID field values |
| Dynamic field not found (code 11) | UI name mismatch | Set `DYNAMIC_FIELD_NAME` to exact `uiName` |
| All attempts failed (code 12) | Wrong field ID | Capture logged IDs; set `DYNAMIC_FIELD_ID` |
| SSL errors | Self-signed cert | Set `VERIFY_SSL=false` (demo) or install CA |

Enable debug:
```bash
LOG_LEVEL=DEBUG python BackBoxDeviceOSUpgrade.py
```

---
## Demo Flow Suggestion
1. Show CSV of device IDs
2. Run script with debug logging
3. Show resolved device IDs + job ID
4. Open BackBox UI and refresh job → devices now listed
5. Show dynamic field updated with `upgrade.zip`
6. (Optional) Re-run with a different file to demonstrate idempotent update

---
## Security Notes
- Never commit real credentials or production artifacts
- Use a service/automation account with least privileges
- Consider rotating credentials after demos

---
## License / Branding
BackBox trademarks and branding remain property of their respective owners. This sample is for demonstration only.

---
## Contact
For enterprise evaluation or feature discussions: https://www.backbox.com/request-a-demo/

---