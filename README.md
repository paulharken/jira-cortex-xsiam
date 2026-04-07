# Cortex XSIAM Jira Sync

A single-file Python script that syncs Palo Alto Cortex XSIAM security cases and standalone issues to Atlassian Jira Cloud. Designed to run as a Cortex XSIAM automation cron job (every 60 seconds).

## What It Does

- **Cortex Cases -> Jira:** Creates Jira tickets for new Cortex cases with full ADF descriptions, severity-based priority, and XDR deep links
- **Jira -> Cortex:** Resolves Cortex cases when Jira tickets are closed (with configurable resolution type mapping)
- **Standalone Issues -> Jira:** Syncs assigned Cortex issues (not linked to cases) to Jira, auto-assigns to the same analyst
- **Bidirectional Closure:** Detects closure from either side and syncs state
- **Severity Sync:** Updates Jira priority when Cortex case severity changes
- **Duplicate Detection:** JQL check before ticket creation to prevent duplicates

## Architecture

```
cortex_jira_sync.py     # Single-file script (~900 lines)
cortex_jira_sync.yml    # XSIAM integration definition (params, commands, cron)
```

**State persistence:** Uses `demisto.setIntegrationContext()` / `demisto.getIntegrationContext()` — a JSON key-value store that survives between cron invocations.

**No external dependencies** beyond `requests` (pre-installed in XSIAM runtime).

## State Schema

```json
{
  "last_poll_ms": 1711900000000,
  "sync_records": {
    "12345": {
      "jira_key": "SEC-100",
      "severity": "HIGH",
      "issue_ids": ["111", "222"],
      "status": "open",
      "created_at": "2026-03-25T10:00:00Z"
    }
  },
  "issue_sync_records": {
    "67890": {
      "jira_key": "SEC-101",
      "status": "open"
    }
  },
  "retry_queue": [],
  "user_cache": {
    "analyst@company.com": "jira-account-id-xxx"
  }
}
```

## Sync Flow (every 60 seconds)

```
1. Load state from integration context
2. Process retry queue (failed ticket creations)
3. Cortex -> Jira: fetch new/changed cases, create/update tickets
4. Check open cases: severity changes, closure detection (both directions)
5. Jira -> Cortex: find closed Jira alerts, resolve Cortex cases
6. Issue sync: fetch assigned standalone issues, create Jira tickets + auto-assign
7. Prune closed records older than 7 days
8. Save state
```

## Configuration

All config is set via XSIAM integration parameters (no `.env` file):

| Parameter | Required | Description |
|-----------|----------|-------------|
| `cortex_base_url` | Yes | Cortex API endpoint |
| `cortex_api_key` | Yes | API authentication key |
| `cortex_api_key_id` | Yes | API key ID |
| `cortex_console_url` | No | Console URL for XDR deep links in Jira tickets |
| `cortex_case_domain` | No | Case domain filter (default: `security`) |
| `jira_site_url` | Yes | Jira site URL (e.g. `https://site.atlassian.net`) |
| `jira_cloud_id` | No | Jira Cloud ID for API routing |
| `jira_email` | Yes | Jira API auth email |
| `jira_api_token` | Yes | Jira API token |
| `jira_project_key` | Yes | Jira project key (e.g. `SEC`) |
| `jira_issue_type` | No | Issue type to create (default: `Alert`) |
| `jira_case_id_field` | No | Custom field ID for Cortex Case ID |
| `jira_issue_id_field` | No | Custom field ID for Cortex Issue ID |
| `jira_xdr_url_field` | No | Custom field ID for XDR URL |
| `resolution_type_map` | No | JSON: Jira status -> Cortex resolve_reason |
| `default_resolution_type` | No | Fallback resolve reason (default: `Resolved - Other`) |
| `max_sync_cases` | No | Max tickets per cycle (default: `0` = unlimited) |

## Resolution Type Map

When a Jira ticket reaches Done, the script reads the Jira changelog to find the pre-Done status, then maps it to a Cortex resolve reason:

```json
{
  "True Positive": "Resolved - True Positive",
  "False Positive": "Resolved - False Positive",
  "Duplicate": "Resolved - Duplicate Case"
}
```

Unmapped statuses fall back to `default_resolution_type`.

## Lineage

Forked from [jira-cortex](../jira-cortex/) (Docker-based microservice with Flask dashboard, SQLite, cost engine). This version strips everything down to core sync logic for XSIAM-native deployment.

**Removed:** Flask dashboard, SQLite, cost engine, Teams notifications, circuit breakers, watchdog, DB backup, setup wizard, analyst rate table.

**Kept:** All sync logic, ADF ticket builder, bidirectional closure, severity sync, duplicate detection, resolution mapping, retry queue.
