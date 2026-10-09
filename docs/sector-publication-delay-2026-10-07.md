# Sector publication delay investigation (cotpy issue #4)

The October 7 sector report was generated successfully, but the scheduled
publisher failed while checking an optional logo on the Desktop. It did not
reach GitHub. The later commit contains the original report, rather than a
report generated six hours later.

## Timeline

All local times below are America/New_York (EDT, UTC−04:00).

| Event | October 7 local time | Evidence |
| --- | --- | --- |
| Scheduled start | 17:30 | Installed `com.fox.sectors.daily` LaunchAgent |
| Actual capture start | 17:40:52 | `sectors/logs/daily.out`: `2026-10-07T21:40:52Z` |
| Snapshot created | 17:41:10 | `20261007T214110Z.json`; brief's Created field |
| Brief written | 17:41:11 | `20261007T214111Z-brief.md` filename |
| Last output / error writes | 17:41:14 / 17:41:15 | Filesystem mtimes of `daily.out` / `daily.err` |
| GitHub commit timestamp | 23:44:56 | Commit author and committer dates: `2026-10-08T03:44:56Z` |

The gap from snapshot creation to commit timestamp is 6 hours, 3 minutes,
46 seconds. Commit timestamps do not independently establish the time a ref
was updated or the time a web deployment became available.

The [published commit](https://github.com/kryztoph/csfox/commit/4da4af242c3eee90eff98ce89a10636059327dde)
is titled `Update published reports`. Its
[sector brief](https://github.com/kryztoph/csfox/blob/4da4af242c3eee90eff98ce89a10636059327dde/reports/sectors/latest-brief.md)
is byte-for-byte identical to the local October 7 brief. Both identify
`As of: 2026-10-07`. SHA-256:
`b18a539bd15e65122b892579c40bf11e5aad4f48a336546519a90c2f33b9339d`.
This verifies report identity and its recorded data date, not independent
accuracy of the underlying market prices.

## Failure path

The installed LaunchAgent invokes the sectors project's `scripts/run_daily.sh`,
which generates the snapshot, brief, tracker, and chart pages, then invokes
`scripts/publish_to_reports_repo.sh`. That wrapper executes
`scripts/publish_to_csfox_gh.py`, targeting `kryztoph/csfox` by default.

The final line of `sectors/logs/daily.err` is:

```text
ERROR: [Errno 1] Operation not permitted: '/Users/fox/Desktop/logo.png'
```

The publisher defaults `SECTORS_LOGO_SOURCE` to that Desktop path. Its
`_publish_files()` calls `LOGO_SOURCE.is_file()` before collecting reports.
An access-denied exception escapes to the top-level error handler, which exits
with status 1. `main()` collects files before its first GitHub request, so
this failure prevents any upload, commit creation, or branch update.

The daily shell runner uses `set -eu`, has no publishing retry, and exits on
that failure. There is no October 7 `sector rotation capture complete` marker.
The same Desktop error appears repeatedly in earlier log entries. The error
is consistent with macOS Desktop privacy restrictions on a background job;
the precise OS permission decision was not independently traced.

This is evidence of a failed scheduled publication, rather than a six-hour
GitHub queue. Available logs do not identify who or what performed the later
successful publication, nor why capture started 10 minutes 52 seconds after
the scheduled time. Sleep/wake behavior is a possible explanation for the
late start, but has not been verified.

## Verification performed

- Read the installed LaunchAgent and the actual sectors runner/publisher,
  rather than assuming cotpy's weekly job owns the sector report.
- Correlated the final October 7 output block, final error, log mtimes, and
  local brief's Created/As of fields.
- Retrieved the public GitHub commit metadata and brief at that exact SHA;
  confirmed equality with the local brief and the SHA-256 above.
- Loaded the sectors publisher without executing its entry point, mocked
  `Path.is_file()` to raise the observed Desktop permission error, and
  confirmed `_publish_files()` fails with zero GitHub subprocess calls.
  This reproduces the code path; it does not test actual launchd permissions.

Authenticated `gh issue view` returned HTTP 401 in this worker environment.
Public read-only API requests succeeded. No GitHub mutations, publication,
LaunchAgent changes, or original-project edits were performed.

## Remediation location and acceptance criteria

The faulty runtime belongs to the separate **sectors** project. Changing
cotpy's publisher would not fix this sector publication path. This PR records
the requested investigation; it does not claim a runtime fix or deployment.

A follow-up implementation in sectors should:

1. Remove the background publisher's dependency on a Desktop file. Prefer a
   project-local asset, or skip an unavailable optional logo with a warning
   while preserving the remote logo. Handle permission errors both when
   checking and reading the logo; required report failures must remain fatal.
2. Log publishing start, success, failure, and commit SHA with timestamps;
   add bounded API timeouts and retry transient network/API failures.
3. Test a denied optional logo and verify required report publication still
   proceeds. Also test denied/missing required reports remain failures.
4. After review and authorized deployment, verify the scheduled LaunchAgent
   reaches its completion marker and publishes the current brief promptly.

Determining the caller of the 23:44 commit or explaining the late scheduled
start requires additional execution or sleep/wake history. Neither is needed
to establish the observed scheduled publishing failure.
