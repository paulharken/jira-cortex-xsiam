## Cortex XSIAM to Jira Cloud Sync

This integration syncs Cortex XSIAM security cases and standalone issues to Atlassian Jira Cloud.

### Features
- Creates Jira tickets from new Cortex XSIAM cases
- Syncs severity changes to Jira priority
- Bidirectional closure: resolving in either system updates the other
- Syncs standalone assigned issues (not linked to cases) to Jira
- Auto-assigns Jira tickets based on Cortex analyst assignment
- Retry queue with exponential backoff for transient failures

### Setup
1. Configure Cortex API credentials (base URL, API key, key ID)
2. Configure Jira Cloud credentials (site URL, email, API token)
3. Set the Jira project key where tickets should be created
4. Optionally configure custom field IDs for case ID, issue ID, and XDR URL
5. Enable "Fetch incidents" and set the interval to 1 minute
6. Configure the resolution type map to match your Jira workflow statuses to Cortex resolve reasons
