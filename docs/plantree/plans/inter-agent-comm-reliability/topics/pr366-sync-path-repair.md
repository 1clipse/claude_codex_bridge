# PR 366 synchronization path repair

Date: 2026-10-06
Mode: status-update
Status: repaired and verified locally; commit and branch push authorized on 2026-10-06; not merged or deployed.
Base: PR 366 head 9e2d197236c61aebbd540fcd3b8cbfbbeaddb94e.

Scope: fix silent omission of unsupported ordinary file paths during input
snapshot and result collection. Keep explicit control/credential/cache exclusions.
Use a dedicated SyncError subtype only for intentional exclusions; scanners catch
that subtype and propagate other path errors. Wire validation still rejects both.

Acceptance: ordinary unsupported input blocks before dispatch; unsupported output
blocks successful completion/receipt; manual rename permits synchronization
recovery without promoting the failed job; explicit exclusions stay uncollected.
Run focused remote, callback, dispatcher and composer regressions.

The trusted-base platform isolation gate remains a separate blocker: the original
PR changes simulated-platform tests and unsupported-platform documentation. Do not
weaken the gate, delete coverage or hide markers to obtain a pass. No deployment,
external provider state change, remote model execution or integration is included.

## Verification

Before repair, six input/output regressions failed (silently running or completing)
and the explicit-exclusion control passed. After repair, the expanded suite passed
**497 tests, 4 skipped**. Coverage includes both worktree and commits publication,
colon/backslash/trailing-space filenames, directory names, path depth/length,
explicit exclusions, and recovery after manual rename. The original independent
review probe also passes. Existing process-crash, callback and dispatch tests are
included; skipped cases require optional sandbox tools or explicit live SSH setup.
No fresh SSH/model test was run for this file-policy-only repair.

Changed Python files parse; git diff --check passes. PR head remains 9e2d19723;
work is isolated on fix/pr366-review-20261006. The existing trusted-base isolation
failure is unresolved and still blocks merge qualification; no platform policy or
coverage was weakened. Prior #354/#356 fixes remain on their separate branches.
