# Cortex XSIAM Jira Sync

A single-file Python script that syncs Palo Alto Cortex XSIAM security cases and standalone issues to Atlassian Jira Cloud. Designed to run as a Cortex XSIAM automation cron job (every 60 seconds).

## What It Does

- **Cortex Cases -> Jira:** Creates Jira tickets for new Cortex cases with full ADF descriptions, severity-based priority, and XDR deep links
- **Jira -> Cortex:** Resolves Cortex cases when Jira tickets are closed (with configurable resolution type mapping)
- **Standalone Issues -> Jira:** Syncs assigned standalone Cortex issues to Jira (see below)
- **Bidirectional Closure:** Detects closure from either side and syncs state
- **Severity Sync:** Updates Jira priority when Cortex case severity changes
- **Duplicate Detection:** JQL check before ticket creation to prevent duplicates
- **Playbook Readiness Check:** Defers Jira ticket creation until all playbooks for a case's issues have completed, preventing sync of incomplete data

## Architecture

```
cortex_jira_sync.py     # Single-file script (~900 lines)
cortex_jira_sync.yml    # XSIAM integration definition (params, commands, cron)
```

**State persistence:** Uses `demisto.setIntegrationContext()` / `demisto.getIntegrationContext()` — a JSON key-value store that survives between cron invocations.

**No external dependencies** beyond `requests` (pre-installed in XSIAM runtime).

**Cortex API key required.** The integration authenticates to the Cortex public API using an API key + key ID pair generated in Cortex Settings > API Keys.

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

## Standalone Issue Sync

When `sync_issues` is enabled, the script syncs standalone Cortex issues to Jira. Not all issues are synced — only those that meet all of the following criteria:

1. **Not linked to a case** — issues that are already part of a Cortex case are handled by the case sync and won't be duplicated as standalone tickets
2. **Assigned to an analyst** — only issues where someone has picked up the work (`assigned_to` is populated). Unassigned issues are ignored.
3. **Not resolved** — resolved issues are skipped
4. **Not already synced** — issues that already have a Jira ticket won't be created again

When a qualifying issue is synced, the script also auto-assigns the Jira ticket to the same analyst (matched by email via the Jira user search API, with results cached in state).

This is off by default. Enable it with the `sync_issues` parameter.

## Configuration

All config is set via XSIAM integration parameters (no `.env` file):

| Parameter | Required | Description |
|-----------|----------|-------------|
| `cortex_base_url` | **Yes** | Cortex API endpoint (e.g. `https://api-yourname.xdr.us.paloaltonetworks.com`) |
| `cortex_api_key` | **Yes** | API authentication key from Cortex Settings > API Keys |
| `cortex_api_key_id` | **Yes** | Numeric ID associated with the API key |
| `cortex_console_url` | **Yes** | Console URL for XDR deep links in Jira tickets (e.g. `https://yourname.xdr.us.paloaltonetworks.com`) |
| `cortex_case_domain` | No | Case domain filter (default: `security`) |
| `jira_site_url` | **Yes** | Jira site URL (e.g. `https://site.atlassian.net`) |
| `jira_cloud_id` | No | Jira Cloud ID for API routing |
| `jira_email` | **Yes** | Jira API auth email |
| `jira_api_token` | **Yes** | Jira API token |
| `jira_project_key` | **Yes** | Jira project key (e.g. `SEC`) |
| `jira_issue_type` | No | Issue type to create (default: `Alert`) |
| `jira_case_id_field` | **Yes** | Custom field ID for Cortex Case ID (e.g. `customfield_10062`). **Required for duplicate detection.** |
| `jira_issue_id_field` | **Yes** | Custom field ID for Cortex Issue ID (e.g. `customfield_10063`). **Required for duplicate detection.** |
| `jira_xdr_url_field` | No | Custom field ID for XDR URL |
| `resolution_type_map` | No | JSON: Jira status -> Cortex resolve_reason |
| `default_resolution_type` | No | Fallback resolve reason (default: `Resolved - Other`) |
| `sync_from_date` | No | Only sync cases/issues updated on or after this date. Uses ISO 8601 format: `YYYY-MM-DD` (e.g. `2026-01-15` for 15 January 2026). Leave empty to sync all. |
| `sync_issues` | No | Sync standalone issues to Jira (default: `false`). Enable to sync issues in addition to cases. |
| `max_sync_cases` | No | Max tickets per cycle (default: `0` = unlimited) |

## Resolution Type Map

When a Jira ticket reaches Done, the script reads the Jira changelog to find the pre-Done status, then maps it to a Cortex resolve reason:

```json
{
  "False Positive": "Resolved - False Positive",
  "Duplicate": "Resolved - Duplicate Case",
  "Known Issue": "Resolved - Known Issue",
  "Security Testing": "Resolved - Security Testing",
  "TP Malicious": "Resolved - TP Malicious",
  "TP Benign": "Resolved - TP Benign",
  "SPAM": "Resolved - SPAM or Marketing"
}
```

Unmapped statuses fall back to `default_resolution_type`.

## Deployment to XSIAM

### Prerequisites

1. **Cortex API key** — Generate at Cortex Settings > API Keys. Note both the key and its numeric ID.
2. **Jira API token** — Generate at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens). The Jira account needs project admin on the target project.
3. **Jira custom fields** (required) — Create three short-text custom fields in your Jira project:
   - Cortex Case ID
   - Cortex Issue ID
   - XDR URL

   Note their field IDs (e.g. `customfield_10062`). Find IDs via Jira Settings > Issues > Custom fields, or `GET /rest/api/3/field`. The Case ID and Issue ID fields are **required** for duplicate detection — without them, the integration will create duplicate tickets on every sync cycle.

### Step 1: Create a Custom Content Pack

1. In XSIAM, go to **Settings > Content > Custom Content**
2. Click **Create New Pack**
3. Name it `Cortex Jira Sync` (or whatever you prefer)

### Step 2: Upload the Integration

1. Inside your content pack, click **Add Content > Integration**
2. Open the **Code Editor** tab
3. Paste the entire contents of `cortex_jira_sync.py` into the Python editor
4. Switch to the **Settings** tab
5. Either:
   - Manually configure each parameter to match `cortex_jira_sync.yml`, OR
   - Use **Import YAML** and upload `cortex_jira_sync.yml` directly (if available in your XSIAM version)
6. Save the integration

### Step 3: Configure an Instance

1. Go to **Settings > Integrations > Instances**
2. Search for `Cortex Jira Sync`
3. Click **Add Instance**
4. Fill in the required parameters:
   - **Cortex API Base URL** — e.g. `https://api-yourname.xdr.us.paloaltonetworks.com`
   - **Cortex API Key** + **API Key ID** — from prerequisites step 1
   - **Cortex Console URL** — e.g. `https://yourname.xdr.us.paloaltonetworks.com`
   - **Jira Site URL** — e.g. `https://yoursite.atlassian.net`
   - **Jira Email** — the API account email
   - **Jira API Token** — from prerequisites step 2
   - **Jira Project Key** — e.g. `SEC`
   - **Jira Case ID Field** + **Issue ID Field** — custom field IDs from prerequisites step 3
5. Fill in optional fields:
   - **Jira XDR URL Field** — custom field ID for the XDR deep link
   - **Resolution Type Map** — JSON mapping Jira pre-Done statuses to Cortex resolve reasons
6. Enable **Fetches incidents** and set **Incidents Fetch Interval** to `1` (minute)
7. Click **Test** — verifies connectivity to both Cortex and Jira
8. Click **Save & Exit**

### Step 4: Verify It's Running

1. Wait 1-2 minutes for the first cron cycle
2. In the War Room, run: `!cortex-jira-status`
   - You should see `last_poll_ms` populated and `open_cases` > 0 (if non-resolved cases exist)
3. Check your Jira project for newly created tickets
4. Verify tickets have:
   - Correct priority (mapped from Cortex severity)
   - XDR deep link in the description (if console URL configured)
   - Cortex Case ID populated in the custom field

### Available Commands

| Command | Description |
|---------|-------------|
| `!cortex-jira-sync` | Manually trigger a full sync cycle |
| `!cortex-jira-status` | Show current state: open/closed counts, retry queue, last poll times |
| `!cortex-jira-reset-state` | Clear all state — next sync does a full initial pull. **Use with caution.** |
| `!cortex-jira-discover-resolutions` | Discover Cortex resolve reasons and cross-check against Jira workflow statuses |

### Resolution Type Discovery

Run `!cortex-jira-discover-resolutions` to automatically build your `resolution_type_map`. The command:

1. Fetches all resolved cases from Cortex and extracts unique `resolve_reason` values
2. Strips the `Resolved - ` prefix to derive expected Jira status names
3. Fetches your Jira project's workflow statuses and cross-checks for matches
4. Outputs a ready-to-paste JSON map and flags any missing Jira statuses you need to create

This is useful during initial setup to ensure your Jira workflow statuses align with Cortex resolution types. Any missing statuses should be added to your Jira workflow before enabling bidirectional closure.

### Troubleshooting

**Test fails with "Cortex connection failed"**
- Verify the API key, key ID, and base URL are correct
- API key must have the required permissions in Cortex Settings > API Keys

**Test fails with "Jira connection failed"**
- Verify the email + token pair is correct
- If using Cloud ID: confirm it at `yoursite.atlassian.net/_edge/tenant_info`
- If not using Cloud ID: ensure `jira_site_url` is the full URL (e.g. `https://yoursite.atlassian.net`)

**Tickets created but no XDR link**
- Set `cortex_console_url` AND `jira_xdr_url_field` — both are required for links

**Duplicate tickets appearing**
- Verify `jira_case_id_field` and `jira_issue_id_field` are set correctly — these are required and power the JQL duplicate check before ticket creation
- If duplicates already exist, close the extras in Jira and run `!cortex-jira-reset-state` to re-sync

**First run creates too many tickets**
- Set `sync_from_date` to limit the initial sync to recent cases (e.g. `2026-01-15` for 15 January 2026, format is `YYYY-MM-DD`)
- Set `max_sync_cases` to a small number (e.g. 10) for initial testing
- Once confirmed working, set to 0 (unlimited) or remove the limit

**State grows too large**
- Closed records are automatically pruned after 7 days
- If you need to force a cleanup, run `!cortex-jira-reset-state` (will re-sync everything)


