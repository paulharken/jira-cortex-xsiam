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
| `sync_issues` | No | Sync standalone issues to Jira (default: `true`). Disable to only sync cases. |
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

## Deployment to XSIAM

### Prerequisites

1. **Cortex XSIAM API key** — Settings > Configurations > API Keys. Create a key with at minimum Cases read/write and Issues read permissions.
2. **Jira API token** — Generate at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens). The Jira account needs project admin on the target project.
3. **Jira custom fields** (recommended) — Create three short-text custom fields in your Jira project:
   - Cortex Case ID
   - Cortex Issue ID
   - XDR URL

   Note their field IDs (e.g. `customfield_10062`). Find IDs via Jira Settings > Issues > Custom fields, or `GET /rest/api/3/field`.

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
4. Fill in all required parameters:
   - **Cortex API Base URL** — e.g. `https://api-yourname.xdr.us.paloaltonetworks.com`
   - **Cortex API Key** — the key value
   - **Cortex API Key ID** — the numeric ID
   - **Jira Site URL** — e.g. `https://yoursite.atlassian.net`
   - **Jira Email** — the API account email
   - **Jira API Token** — from step 1
   - **Jira Project Key** — e.g. `SEC`
5. Fill in optional fields:
   - **Cortex Console URL** — enables XDR deep links in Jira ticket descriptions
   - **Jira Case ID / Issue ID / XDR URL fields** — the custom field IDs from prerequisites
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
   - Cortex Case ID in the custom field (if configured)

### Available Commands

| Command | Description |
|---------|-------------|
| `!cortex-jira-sync` | Manually trigger a full sync cycle |
| `!cortex-jira-status` | Show current state: open/closed counts, retry queue, last poll times |
| `!cortex-jira-reset-state` | Clear all state — next sync does a full initial pull. **Use with caution.** |

### Troubleshooting

**Test fails with "Cortex connection failed"**
- Verify the API key hasn't expired
- Check the base URL ends with the domain, no trailing path (e.g. no `/public_api/v1`)
- Ensure the XSIAM instance has outbound HTTPS access (if using external API calls)

**Test fails with "Jira connection failed"**
- Verify the email + token pair is correct
- If using Cloud ID: confirm it at `yoursite.atlassian.net/_edge/tenant_info`
- If not using Cloud ID: ensure `jira_site_url` is the full URL (e.g. `https://yoursite.atlassian.net`)

**Tickets created but no XDR link**
- Set `cortex_console_url` AND `jira_xdr_url_field` — both are required for links

**Duplicate tickets appearing**
- Set `jira_case_id_field` to enable duplicate detection (JQL check before creation)
- If duplicates already exist, close the extras in Jira and run `!cortex-jira-reset-state` to re-sync

**First run creates too many tickets**
- Set `max_sync_cases` to a small number (e.g. 10) for initial testing
- Once confirmed working, set to 0 (unlimited) or remove the limit

**State grows too large**
- Closed records are automatically pruned after 7 days
- If you need to force a cleanup, run `!cortex-jira-reset-state` (will re-sync everything)

---

## Lineage

Forked from [jira-cortex](../jira-cortex/) (Docker-based microservice with Flask dashboard, SQLite, cost engine). This version strips everything down to core sync logic for XSIAM-native deployment.

**Removed:** Flask dashboard, SQLite, cost engine, Teams notifications, circuit breakers, watchdog, DB backup, setup wizard, analyst rate table.

**Kept:** All sync logic, ADF ticket builder, bidirectional closure, severity sync, duplicate detection, resolution mapping, retry queue.
