"""
Local mock of the Cortex XSIAM `demisto` module.

Loads config from .env (or env vars), persists integration context to a local
JSON file, and prints log/results to stdout.  Enough to run cortex_jira_sync.py
outside of XSIAM for testing.
"""

import json
import os
import sys
from pathlib import Path

# ── internal state ──────────────────────────────────────────────────────────

_params: dict = {}
_command: str = "fetch-incidents"
_integration_context: dict = {}
_state_file: Path = Path(__file__).parent / "local_state.json"


# ── bootstrap helpers ───────────────────────────────────────────────────────

def _load_env(path=None):
    """Crude .env loader (no shell expansion). Supports quoted values."""
    if path is None:
        path = os.environ.get(
            "DEMISTO_ENV_FILE",
            str(Path(__file__).parent.parent / "jira-cortex" / ".env"),
        )
    if not Path(path).exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip("'\"")
            os.environ.setdefault(key.strip(), value)


def _init_params():
    """Build the params dict that demisto.params() returns."""
    global _params
    _load_env()
    _params = {
        "cortex_base_url":        os.environ.get("CORTEX_BASE_URL", ""),
        "cortex_api_key":         os.environ.get("CORTEX_API_KEY", ""),
        "cortex_api_key_id":      os.environ.get("CORTEX_API_KEY_ID", ""),
        "cortex_console_url":     os.environ.get("CORTEX_CONSOLE_URL", ""),
        "cortex_case_domain":     os.environ.get("CORTEX_CASE_DOMAIN", "security"),
        "jira_site_url":          os.environ.get("JIRA_SITE_URL", ""),
        "jira_cloud_id":          os.environ.get("JIRA_CLOUD_ID", ""),
        "jira_email":             os.environ.get("JIRA_EMAIL", ""),
        "jira_api_token":         os.environ.get("JIRA_API_TOKEN", ""),
        "jira_project_key":       os.environ.get("JIRA_PROJECT_KEY", ""),
        "jira_issue_type":        os.environ.get("JIRA_ISSUE_TYPE", "Alert"),
        "jira_case_id_field":     os.environ.get("JIRA_CASE_ID_FIELD", ""),
        "jira_issue_id_field":    os.environ.get("JIRA_ISSUE_ID_FIELD", ""),
        "jira_xdr_url_field":     os.environ.get("JIRA_XDR_URL_FIELD", ""),
        "resolution_type_map":    os.environ.get("RESOLUTION_TYPE_MAP", "{}"),
        "default_resolution_type": os.environ.get("DEFAULT_RESOLUTION_TYPE", "Resolved - Other"),
        "max_sync_cases":         os.environ.get("MAX_SYNC_CASES", "0"),
        "sync_issues":            os.environ.get("SYNC_ISSUES", "false").lower() in ("true", "1", "yes"),
        "sync_from_date":         os.environ.get("SYNC_FROM_DATE", ""),
    }


def _load_state():
    """Load persisted integration context from local JSON file."""
    global _integration_context
    if _state_file.exists():
        try:
            _integration_context = json.loads(_state_file.read_text())
        except (json.JSONDecodeError, OSError):
            _integration_context = {}
    else:
        _integration_context = {}


def _save_state():
    """Persist integration context to local JSON file."""
    _state_file.write_text(json.dumps(_integration_context, indent=2))


# ── demisto API surface ─────────────────────────────────────────────────────

def params() -> dict:
    return _params


def command() -> str:
    return _command


def getIntegrationContext() -> dict:
    return _integration_context


def setIntegrationContext(ctx: dict):
    global _integration_context
    _integration_context = ctx
    _save_state()


def info(msg: str):
    print(f"[INFO]  {msg}")


def debug(msg: str):
    print(f"[DEBUG] {msg}")


def error(msg: str):
    print(f"[ERROR] {msg}", file=sys.stderr)


def results(result):
    print(f"[RESULT] {result}")


def incidents(inc_list: list):
    if inc_list:
        print(f"[INCIDENTS] {json.dumps(inc_list, indent=2)}")


def executeCommand(cmd: str, args: dict):
    """Mock — not implemented locally. CortexClient detects local mode and uses public API instead."""
    raise NotImplementedError(f"executeCommand('{cmd}') is not available in local mode")


# callingContext is absent in the mock — CortexClient checks for this to detect XSIAM runtime
# Deliberately not defined so that `demisto.callingContext` raises AttributeError


# ── setup on import ─────────────────────────────────────────────────────────

def _setup(cmd: str = "fetch-incidents"):
    global _command
    _command = cmd
    _init_params()
    _load_state()


# Auto-init with default command; run_local.py overrides via _setup()
_setup()
