# Recurring stale reports: investigation

The original project's `logs/weekly.log` records intermittent failures in the
Saturday job. A weekly schedule made a single failed run visible for an entire
week. The evidence supports several failure modes, rather than one weekly bug:

| Run | Observed failure |
| --- | --- |
| June 27, 2026 | CFTC Disaggregated request timed out; freshness check stopped generation. |
| July 25 and August 1 | GitHub blob upload failed; reports did not reach the reports branch. |
| August 22 | CFTC DNS resolution failed; a later retry at 09:36 succeeded. |
| August 29 | GitHub authentication request failed with `network is down`. |
| September 12 morning | GitHub blob request returned HTTP 400 asking for resubmission. Noon recovery later succeeded. |
| September 19–21 | Generation and publishing stretched across days. Branch update returned non-fast-forward HTTP 422; later retries exhausted API timeouts. |

Long elapsed times are consistent with the Mac suspending an unattended job;
the logs alone do not prove sleep was the sole cause. The original installed
LaunchAgent was inspected read-only and has both Saturday 7 a.m. and noon
triggers. Its latest exit code was zero; the October 3 noon run's status recorded
`completed` with `published: true` and its log recorded live dashboard verification.
This is historical run evidence, not a new live deployment test.

## Changes

The ticket branch starts before existing recovery work in the original project.
It selectively incorporates that work without the later dashboard, pricing,
or branding edits: bounded stage and API retries, OS locking, status records,
unchanged-blob skipping, required-chart checks, and Pages commit/content checks.
It also includes the existing local fixes for refreshing mutable archives and
weekly endpoints, rejecting failed or stale weekly downloads, reusing historical
archives, a noon fallback, and macOS idle-sleep prevention.

The default maximum report age is 10 days. This rejects the preceding Tuesday's
report on a normal Saturday (11 days old), but accepts a recent late-December
report in January before a new annual archive exists. For a known release delay,
`COTPY_MAX_REPORT_AGE_DAYS` permits an explicit positive override.

## Recovery limits

The job still runs on a local Mac. `caffeinate -i` prevents idle sleep during a
run, but does not wake the computer or prevent lid-close sleep. Extended network
outages or upstream release delays can exhaust retries. Inspect
`logs/weekly-status.json` and `logs/weekly.log`, restore availability, then rerun
`scripts/run_cotpy_weekly.sh`. A non-fast-forward publication is retried as a
whole publish stage against the latest branch head; no force push is used.

No scheduler installation, original-project modification, GitHub write, or
live deployment was performed for this ticket. Installing the committed changes
and any LaunchAgent reload remain operational steps after review.

## Ticket validation

- `python -m unittest discover -s tests -v`: 22 tests passed, including
  subprocess termination, lock contention, stage/API retries, stale and invalid
  report rejection, New Year handling, and Pages verification with mocked API
  responses. The dry-run test asserts that no GitHub calls occur.
- `main.py --analyze --signals --export --market-charts`: exit 0 against a
  separate copy of the real cache; 38 markets and 80 chart artifacts generated.
- `report.py` and `summary_report.py`: both exited 0 and saved their reports.
- Weekly freshness validation accepted both cached reports dated 2026-09-29.
- `COTPY_PUBLISH_DRY_RUN=1`: exit 0 and listed the generated artifacts without
  contacting GitHub.
- Shell syntax, plist lint, and `git diff --check` passed.

Commands used the original virtualenv and a copied Matplotlib font cache.
Live CFTC downloads and Pages publishing were not exercised; network failure
recovery and deployment checks were tested with controlled responses.
