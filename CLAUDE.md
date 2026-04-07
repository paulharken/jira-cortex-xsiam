# Cortex XSIAM Jira Sync -- CLAUDE.md

Project-level context for AI-assisted development. Read this at the start of every session.

---

## What This Is

A single-file Python script that syncs Palo Alto Cortex XSIAM cases and standalone issues to Atlassian Jira Cloud. Runs as a Cortex XSIAM automation cron job every 60 seconds.

- **Script:** `cortex_jira_sync.py`
- **Integration def:** `cortex_jira_sync.yml`
- **Runtime:** XSIAM Python automation sandbox
- **State:** `demisto.setIntegrationContext()` / `demisto.getIntegrationContext()` (JSON blob)
- **Dependencies:** `requests` only (pre-installed in XSIAM)
- **Forked from:** `../jira-cortex/` (Docker microservice version)

---

## Critical API Knowledge

### Cortex Cases API
- Filter field is `status_progress` -- NOT `status`
- Time field is `last_update_time` -- NOT `modification_time`
- Valid operators: `in`, `nin`, `gte`, `lte`, `CONTAINS_IN_LIST`, `NOT_CONTAINS_IN_LIST`
- `neq`, `eq`, `not_in` do NOT work -- return 400
- Pagination uses `FILTER_COUNT` not `TOTAL_COUNT`
- Case resolution endpoint: `POST /public_api/v1/case/update/{case_id}` -- returns **204 No Content** (empty body, do NOT call `.json()`)
- `resolve_reason` and `status_progress: Resolved` must be sent TOGETHER
- Severity in responses is **lowercase**: `"high"`, `"medium"`, etc.

### Valid Cortex `resolve_reason` Values
```
Resolved - False Positive
Resolved - True Positive
Resolved - Duplicate Case
Resolved - Known Issue
Resolved - Other
Resolved - Security Testing
Resolved - Dismissed
Resolved - Fixed
Resolved - Risk Accepted
```
`Resolved - Auto Resolve` is system-only -- returns 400 if sent via API.

### Cortex Issues API
- Much more limited: only `in` and `gte`/`lte` operators -- no `nin`
- Filter field for time: `observation_time` -- NOT `creation_time`
- Filter field for status: `status.progress` (dot-notation literal)
- Issue ID field is `id` in responses, NOT `issue_id`
- Severity in responses is UPPERCASE: `"HIGH"`, `"MEDIUM"`, `"CRITICAL"`
- Cannot filter "assigned issues" via API -- `assigned_to` only supports `in` with specific values, NOT `neq null`. Must filter in Python post-fetch.

### Jira API
- Use `POST /rest/api/3/search/jql` -- the old `GET /rest/api/3/search` is gone (410)
- If `JIRA_CLOUD_ID` is empty, use `JIRA_SITE_URL` directly -- NOT the cloud routing URL
- Dropdown/select custom fields must write as `{"value": "Finance"}` not plain string
- Changelog returns oldest-to-newest; `transitions[-1]` is the most recent transition
- User search: `GET /rest/api/3/user/search?query={email}` -- filter by `accountType == "atlassian"`

---

## Sync Flow

```
Every 60 seconds (XSIAM cron):
  1. Load state from integration context
  2. Process retry queue
  3. sync_cortex_to_jira()  -- new/changed cases -> Jira tickets
  4. check_open_cases()     -- severity sync, bidirectional closure detection
  5. sync_jira_to_cortex()  -- Jira closed alerts -> Cortex resolve
  6. sync_issues_to_jira()  -- assigned standalone issues -> Jira tickets + auto-assign
  7. Prune closed records > 7 days old
  8. Save state to integration context
```

---

## State Schema

```json
{
  "last_poll_ms": 1711900000000,
  "last_jira_poll_iso": "2026-03-25T10:00:00+00:00",
  "sync_records": {
    "<case_id>": {
      "jira_key": "SEC-100",
      "severity": "HIGH",
      "issue_ids": ["111", "222"],
      "status": "open",
      "created_at": "2026-03-25T10:00:00Z"
    }
  },
  "issue_sync_records": {
    "<issue_id>": {
      "jira_key": "SEC-101",
      "status": "open"
    }
  },
  "retry_queue": [
    {"case_id": 99999, "case_json": "{...}", "attempts": 1, "next_retry_ms": 1711900060000}
  ],
  "user_cache": {
    "analyst@company.com": "jira-account-id-xxx"
  }
}
```

---

## Key Patterns

### Analyst Auto-Assignment
1. Cortex case/issue has `assigned_user_mail` or `assigned_to` (email)
2. Check `user_cache` in state -- if cached, use Jira account ID directly
3. If not cached, call `GET /rest/api/3/user/search?query={email}`
4. Cache the email -> accountId mapping in state
5. Call `PUT /rest/api/3/issue/{key}/assignee` with the account ID

### Standalone Issue Detection
An issue is "standalone" if:
1. Its `id` does NOT appear in any case's `issue_ids` (check `sync_records`)
2. `assigned_to` is not null/empty (filter in Python, API can't do this)
3. `status.progress` is not "RESOLVED"

### Closure Resolution Map
When Jira ticket hits Done:
1. Fetch Jira changelog -- last transition's `from_status` = pre-Done status name
2. Look up in `resolution_type_map` config param (JSON) -> Cortex `resolve_reason`
3. Fallback: `default_resolution_type`
4. Call Cortex `update_case(case_id, status="Resolved", reason=..., comment="Resolved via Jira {key}")`

### Retry Queue
- Failed ticket creations go into `retry_queue` in state
- Max 5 attempts per case, exponential backoff (2^n minutes)
- Processed at the start of each cycle
- Abandoned entries logged to war room

---

## Common Mistakes to Avoid

- Never call `.json()` on Cortex case/update response -- it's 204 No Content
- Never use `status` as a Cortex filter field -- use `status_progress`
- Never use `modification_time` -- use `last_update_time`
- Never use `neq` operator in Cortex -- use `nin`
- Never leave `JIRA_CLOUD_ID` blank while using `https://api.atlassian.com/ex/jira/` -- use site URL directly
- Jira dropdown fields need `{"value": "X"}` not `"X"`
- Cortex Issues API: `id` not `issue_id`, severity UPPERCASE, status field is `status.progress`
- XSIAM integration context is JSON only -- no complex Python objects, no sets (use lists)
- `requests` response: use `resp.ok` or `resp.raise_for_status()`, NOT httpx patterns

---

## What's NOT in This Version

Removed from the Docker version (jira-cortex):
- Flask dashboard and all web UI
- SQLite database
- Cost engine (analyst rates, billable time, BU attribution, MTTR/MTTC)
- Teams webhook notifications
- Circuit breakers
- Watchdog thread
- DB backup
- Setup wizard
- Config hot-reload
- Sync pause/resume

Reporting and analytics are handled by PowerBI connecting to Jira/Cortex directly.
