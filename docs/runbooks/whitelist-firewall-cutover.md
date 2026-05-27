# Whitelist Cutover and Firewall PowerShell Backend Runbook

Updated: 2026-05-27

This runbook intentionally splits the two operational changes into separate
rollouts. Do not remove whitelist compatibility code in the same deployment
that migrates production data, and do not make PowerShell the default firewall
write backend before a Windows Administrator canary passes.

## 1. Whitelist Data Cutover

Preconditions:

- A current MongoDB backup exists and restore has been tested.
- Staging is running the collection-first dual-path code.
- No production write command is run outside a maintenance window.

Staging sequence:

```powershell
.venv\Scripts\python.exe server\scripts\migrations\2026_backfill_group_whitelist_entry_ids.py --dry-run
.venv\Scripts\python.exe server\scripts\migrations\2026_backfill_group_whitelist_entry_ids.py --write

.venv\Scripts\python.exe server\scripts\migrations\2026_migrate_group_whitelist_to_entries.py --json --fail-on-invalid
.venv\Scripts\python.exe server\scripts\migrations\2026_migrate_group_whitelist_to_entries.py --write --json --fail-on-invalid
```

Only run the backfill `--write` command when the dry-run reports rows that
need `_id` stamping or normalization.

Pass criteria:

- `entries_skipped_invalid` is `0`.
- New group whitelist writes create rows in `whitelist_entries`.
- `groups.whitelist[]` is not appended for new group writes.
- API/UI returns real Mongo `_id` values, never new `group::...` IDs.
- `pytest server\tests\test_whitelist_and_logs.py -q -x --tb=short` passes.
- Browser smoke for whitelist pages passes against staging.

Production sequence:

1. Take and verify MongoDB backup.
2. Run the same dry-run commands and save output.
3. Run `--write` during the maintenance window.
4. Restart server and run CRUD/RBAC/agent-sync smoke.
5. Keep embedded fallback and pseudo-ID support for at least one release.

Compatibility observation:

- Search server logs for `legacy_group_pseudo_id_used`.
- If any hit appears after the migration, do not remove fallback code yet.
- When the log marker stays at zero for a full release window, plan a follow-up
  release that removes pseudo-ID parsing and embedded `groups.whitelist[]`
  merge fallback.

Rollback:

- Prefer restoring the MongoDB backup if migration data is wrong.
- The current dual-path code can continue reading legacy embedded rows while
  the issue is investigated.

## 2. Firewall PowerShell Backend Canary

Preconditions:

- A physical or console-accessible Windows machine is available.
- The agent is launched as Administrator.
- The operator can restore firewall policy without relying only on RDP.
- SAINT firewall snapshot exists or current Windows firewall policy is recorded.

Canary environment:

```powershell
$env:FIREWALL_WRITE_BACKEND = "powershell"
$env:SAINT_FIREWALL_PROVIDER = "netsecurity"
```

Smoke sequence:

1. Start the agent with firewall enabled and `whitelist_only` mode.
2. Verify self-allow rules exist for agent HTTPS/DNS traffic.
3. Verify whitelist allow rules are created for configured IPs/domains.
4. Verify Default Deny outbound policy is active.
5. Verify DNS, server registration, heartbeat, and log sender still work.
6. Restart the agent and confirm no duplicate managed rules are created.
7. Change whitelist on the server and confirm add/remove sync updates rules.
8. Use GUI Restore Firewall and confirm SAINT rules are removed and profile
   policy returns to the saved snapshot/default.

Pass criteria:

- `pytest agent\tests -q --tb=short` passes before canary.
- No network lockout occurs.
- Restart is idempotent.
- Restore snapshot works from the GUI.
- Operator can roll back by setting `FIREWALL_WRITE_BACKEND=netsh`.

Default switch:

- Keep `netsh` as default until at least one lab/canary machine passes.
- In a later release, change default write backend to NetSecurity/PowerShell
  when available, but keep `FIREWALL_WRITE_BACKEND=netsh` as the documented
  escape hatch.
