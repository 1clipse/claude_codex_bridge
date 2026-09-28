# v8.7.3 release qualification

Date: 2026-09-28
Role: evidence
Status: preparation; publication not yet verified
Related: [release notes](../../../../releases/v8.7.3.md),
[composer evidence](composer-model-independence-20260927.md),
[real Claude qualification](claude-continuous-queue-live-20260927.md)

## Source and scope

Previous release: v8.7.2 (`91fb0a4d2`). Base main: `502e5e558`, including
PR #361. Fix commit `2b5827c16` replaces the Codex model-prefix dependency
and adds three regression files plus verification records. Claude/OMP production
adapters are unchanged. Native Claude plugin investigation is evidence only.

Owner follow-up clarified a second pending source slice: six V3 preview roles
must no longer appear in install/update onboarding suggestions. Commit
`937720a7d` promotes the original local filter and regression tests. This was
absent from v8.7.2 and the initial candidate; the older V1/V2 config-panel filter
was already shipped and must not be confused with it. The new scope passed
188 update/RolePack/config-UI tests. Explicit installation, installed-role
updates and missing-source diagnostics remain intact. Final CI must include
this commit. The original workspace patch is preserved.

The original workspace and unrelated dirty changes remain untouched. Common
release metadata and platform-owned version pointers are separate changes;
the trusted-base ownership checker is not modified. Version 8.7.3 and tag
v8.7.3 were absent from npm and the remote at preparation time. Legacy local
v6.1.2/v6.1.3 tag conflicts were left untouched; main was fetched without tags.

## Local checks

- Python 3.12: 322 focused composer, FIFO, Claude start/poll/activation,
  reply-delivery and execution-service tests passed in 1.83 seconds.
- README/package version visibility and npm runner: 6 passed in 1.72 seconds.
- Bilingual release-note validator passed; manual review preserves matching
  issue references, upgrade requirements, deferred plugin and layout limits.
- `npm pack --dry-run --json`: version 8.7.3, 19 allowlisted files; no runtime
  homes, credentials, native-probe plugin or experimental IPC included.
- `git diff --check` passed.

Earlier real qualification covers 19 Claude jobs with one attempt each,
including three result chains and fixed-deadline/early-clear FIFO behavior.
The native API probe separately established important non-readiness limits;
it is not an additional real model communication pass.

## Remaining gates

Remote Linux/macOS, lifecycle/provider blackbox, real platform, ownership and
package gates must finish before tagging. Confirm the combined common and
platform version identity, then verify GitHub artifacts/checksums, npm latest
and a clean public installation. Append receipts after completion; do not
infer publication from this preparation record.

CI follow-up: the first provider-blackbox and real-platform runs exposed a
stub layout mismatch. Its Codex footer lacked the blank separator present in
native captures. Commit `87fa25b19` corrects only the stub's spacing and cursor
position; 21 targeted stub/lifecycle/adapter checks passed (75 deselected).
The guard was not relaxed. Combined release/package checks passed 44 cases;
Linux candidate archive built successfully. Fresh CI is required on the update.

Local complete communication matrix passed mixed providers, broadcast, dual
Codex/Claude/Gemini, cross-project isolation and cleanup. An earlier harness
launch from the source cwd was rejected by `ccb_test` isolation checks; it was
stopped/cleaned through project control commands and rerun from an authorized
external cwd with caller/provider-home environment removed. The rejected run
is not counted as a pass.
