"""BackBox Device OS Upgrade automation script (modernized).

Features:
 - Environment-based configuration (.env supported)
 - Structured functions with type hints
 - Logging instead of prints
 - Robust device lookup & job modification
 - New dynamic field update API via PUT updateTaskJobDynamicFields
 - Graceful error handling & exit codes
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any

import requests
from urllib3.exceptions import InsecureRequestWarning

try:
    from dotenv import load_dotenv
    _DOTENV_AVAILABLE = True
except ImportError:
    _DOTENV_AVAILABLE = False

# ---------------------------------------------------------------------------
# Setup logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress only the single warning from urllib3 needed (optional SSL verify disable).
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------
REQUIRED_VARS = [
    "BACKBOX_IP",
    "BACKBOX_USER",
    "BACKBOX_PASSWORD",
    "JOB_TO_EXECUTE",
    "JOB_FILE_NAME",
    "DEVICES_FILE",
]


def load_config() -> Dict[str, Any]:
    if _DOTENV_AVAILABLE and os.path.exists('.env'):
        load_dotenv()
        logger.debug("Loaded environment variables from .env")
    missing = [v for v in REQUIRED_VARS if not os.getenv(v)]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(2)
    cfg = {
        "ip": os.getenv("BACKBOX_IP"),
        "user": os.getenv("BACKBOX_USER"),
        "password": os.getenv("BACKBOX_PASSWORD"),
        "job_name": os.getenv("JOB_TO_EXECUTE"),
        "job_file_name": os.getenv("JOB_FILE_NAME"),
        "devices_file": os.getenv("DEVICES_FILE"),
        "dynamic_field_name": os.getenv("DYNAMIC_FIELD_NAME", "IOS bin File"),
        "dynamic_field_id_override": os.getenv("DYNAMIC_FIELD_ID"),
        "verify_ssl": os.getenv("VERIFY_SSL", "false").lower() == "true",
    }
    return cfg


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def read_devices(path: Path) -> List[str]:
    devices: List[str] = []
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        first = True
        for row in reader:
            if not row:
                continue
            first_col = row[0].strip()
            if first and first_col.lower() in {"external_id", "device_id", "id"}:
                first = False
                continue
            first = False
            if first_col:
                devices.append(first_col)
    unique = sorted(set(devices))
    logger.info("Loaded %d device external IDs", len(unique))
    return unique


def login(session: requests.Session, base_url: str, username: str, password: str, verify: bool) -> None:
    logger.debug("Initiating login sequence to %s", base_url)
    resp = session.get(base_url, verify=verify)
    headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8'}
    data = {'j_username': username, 'j_password': password}
    login_resp = session.post(base_url + '/j_security_check', headers=headers, data=data, verify=verify)
    if not login_resp.ok:
        logger.error("Login failed: %s %s", login_resp.status_code, login_resp.text[:200])
        sys.exit(3)
    logger.info("Authenticated to BackBox")


def upload_file(session: requests.Session, internal_api: str, filepath: Path, verify: bool) -> str:
    if not filepath.exists():
        logger.error("Upgrade file not found: %s", filepath)
        sys.exit(4)
    with filepath.open('rb') as fh:
        files = {"file": fh}
        resp = session.post(internal_api + "taskfile/0", files=files, verify=verify)
    if not resp.ok:
        logger.error("File upload failed: %s %s", resp.status_code, resp.text[:200])
        sys.exit(5)
    try:
        file_id = resp.json().get("id")
    except Exception:
        logger.error("Upload response not JSON")
        sys.exit(5)
    if not file_id:
        logger.error("Upload response missing id")
        sys.exit(5)
    logger.info("File uploaded successfully with id %s", file_id)
    return file_id


def fetch_device_id(session: requests.Session, external_api: str, ext_id: str, verify: bool) -> Optional[int]:
    resp = session.get(external_api + f"devicesbyExternalId/{ext_id}", verify=verify)
    if not resp.ok:
        logger.warning("Device lookup failed (%s): %s", ext_id, resp.status_code)
        return None
    try:
        data = resp.json()
    except Exception:
        logger.warning("Non-JSON device response for %s", ext_id)
        return None
    if not isinstance(data, list) or not data:
        logger.warning("No device found for external ID %s", ext_id)
        return None
    return data[0].get('deviceId')


def resolve_job_id(session: requests.Session, external_api: str, job_name: str, verify: bool) -> int:
    resp = session.get(external_api + "taskJobs", verify=verify)
    if not resp.ok:
        logger.error("Failed to retrieve job list: %s", resp.status_code)
        sys.exit(6)
    for item in resp.json():
        if item.get('name') == job_name:
            job_id = item.get('backup_JOB_ID')
            if job_id is not None:
                logger.info("Found job '%s' with id %s", job_name, job_id)
                return job_id
    logger.error("Job '%s' not found", job_name)
    sys.exit(7)


def add_devices_to_job(session: requests.Session, external_api: str, job_id: int, device_ids: List[int], verify: bool) -> None:
    resp = session.get(external_api + f"taskJob/{job_id}", verify=verify)
    if not resp.ok:
        logger.error("Failed to fetch job details: %s", resp.status_code)
        sys.exit(8)
    job_data = resp.json()
    job_data["itemsIN_BackupJob"] = [{"itemId": did, "itemType": 0} for did in device_ids]
    upd = session.put(external_api + "taskJob/", json=job_data, verify=verify)
    if not upd.ok:
        logger.error("Failed to update job devices: %s %s", upd.status_code, upd.text[:200])
        sys.exit(9)
    logger.info("Added %d devices to job %s", len(device_ids), job_id)


def update_dynamic_field(
    session: requests.Session,
    internal_api: str,
    job_id: int,
    job_file_name: str,
    field_display_name: str,
    field_id_override: Optional[str],
    verify: bool,
) -> None:
    empty_payload = json.loads('[]')
    fetch = session.put(
        internal_api + f"tasks/jobs/getTaskJobDynamicFields/{job_id}",
        json=empty_payload,
        verify=verify,
    )
    if not fetch.ok:
        logger.error("Failed to fetch dynamic fields: %s %s", fetch.status_code, fetch.text[:200])
        sys.exit(10)
    try:
        dyn_fields = fetch.json()
    except Exception:
        logger.error("Dynamic fields fetch not JSON")
        sys.exit(10)

    logger.debug("Dynamic fields fetched: %s", dyn_fields)

    candidates: List[int] = []
    chosen: Optional[int] = None
    if field_id_override:
        try:
            chosen = int(field_id_override)
            logger.info("Using override dynamic field ID %s", chosen)
        except ValueError:
            logger.warning("Invalid DYNAMIC_FIELD_ID override '%s' ignored", field_id_override)
            chosen = None
    if chosen is None:
        for f in dyn_fields:
            if f.get("uiName") == field_display_name:
                for key, val in f.items():
                    if 'id' in key.lower() and isinstance(val, int):
                        candidates.append(val)
                break
        if not candidates:
            logger.error("Dynamic field '%s' not found. Available: %s", field_display_name,
                         ", ".join(f.get('uiName', '<none>') for f in dyn_fields))
            sys.exit(11)
        logger.info("Candidate dynamic field IDs: %s", candidates)

    # Attempt update with each candidate until success
    attempt_list = [chosen] if chosen is not None else candidates
    update_url = internal_api + "tasks/jobs/updateTaskJobDynamicFields"
    headers = {"Accept": 'application/json', "Content-Type": 'application/json'}
    for candidate in attempt_list:
        payload = {
            "jobID": job_id,
            "dynamicFieldIDsAndValues": [
                {"dynamicFieldID": candidate, "value": job_file_name}
            ],
        }
        logger.info("Attempting dynamic field update with ID %s", candidate)
        upd = session.put(update_url, json=payload, headers=headers, verify=verify)
        if upd.ok:
            logger.info("Dynamic field '%s' updated with file '%s' (ID used: %s)", field_display_name, job_file_name, candidate)
            return
        logger.warning("Update attempt failed (ID %s): %s %s", candidate, upd.status_code, upd.text[:200])
    logger.error("All dynamic field update attempts failed")
    sys.exit(12)


def main() -> int:
    cfg = load_config()
    base_url = f"https://{cfg['ip']}"
    external_api = base_url + "/rest/data/api/"
    internal_api = base_url + "/rest/data/"

    devices_file = Path(cfg['devices_file'])
    devices = read_devices(devices_file)
    if not devices:
        logger.error("No devices to process. Exiting.")
        return 1

    verify = cfg['verify_ssl']

    with requests.Session() as session:
        login(session, base_url, cfg['user'], cfg['password'], verify)
        upload_file(session, internal_api, Path(cfg['job_file_name']), verify)

        # Resolve device IDs
        resolved_ids: List[int] = []
        for ext in devices:
            dev_id = fetch_device_id(session, external_api, ext, verify)
            if dev_id is not None:
                resolved_ids.append(dev_id)
        if not resolved_ids:
            logger.error("No device IDs resolved. Exiting.")
            return 1
        logger.info("Resolved %d/%d device IDs", len(resolved_ids), len(devices))

        job_id = resolve_job_id(session, external_api, cfg['job_name'], verify)
        add_devices_to_job(session, external_api, job_id, resolved_ids, verify)
        update_dynamic_field(
            session,
            internal_api,
            job_id,
            cfg['job_file_name'],
            cfg['dynamic_field_name'],
            cfg['dynamic_field_id_override'],
            verify,
        )
    return 0


if __name__ == "__main__":
    try:
        code = main()
        sys.exit(code)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(130)