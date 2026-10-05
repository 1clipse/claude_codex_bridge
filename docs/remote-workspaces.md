# Experimental remote workspace transactions

This opt-in interface separates the workspace transaction from provider terminal
transport. A local CCB controller can dispatch to a remote worker, validate the
returned files and Git objects, and only then publish completion and callbacks.
The normal local-agent path remains unchanged.

This is an experimental Linux-to-Linux interface (including a WSL2 controller),
using the Claude pane-backed provider. Local-only projects do not load its
Linux-specific modules. Selecting a remote profile on another controller OS
fails explicitly; Windows and macOS remote controllers are not yet supported.

## Configuration and deployment

An agent using a dedicated Git worktree selects `remote_workspace = "profile"`.
A profile name is an opt-in selector, not a remote address or executable. Keep the
existing project-command approval for the provider command template; `-s` does
not approve a project-authored shell wrapper.

A controller-owned JSON file outside the project, identified by
`CCB_REMOTE_WORKSPACES_FILE`, supplies that profile:

```json
{
  "profile": {
    "host": "worker-ssh-alias",
    "project_root": "/home/controller/project",
    "local_workspace": "/home/controller/project/.ccb/workspaces/worker",
    "agent_name": "worker",
    "remote_root": "/home/worker/.local/share/ccb-unique-project",
    "workspace_id": "unique-project-worker-123",
    "include": ["src", "tests", "README.md"],
    "publish": "worktree",
    "timeout_seconds": 60,
    "ssh_config": "/home/controller/private/ssh-config",
    "retry_attempts": 3,
    "terminal": {
      "session_id": "86d57a39-40e0-46f8-8501-0bf13ae7de57",
      "reconnect_seconds": 300,
      "transcript_limit_mb": 128
    }
  }
}
```

`ssh_config` is optional. Both configuration files must be regular, owned by the
controller and not group/world writable; symlink components are refused. SSH
pins a known host, disables forwarding and connection multiplexing, and transfers
JSON over stdin/stdout. A private network such as Tailscale changes the SSH
address, not the workspace protocol.

The generic adapter is `tools/remote_provider.py --profiles FILE --profile NAME
{command}` in the agent's approved `provider_command_template`. Use CCB's
isolated local provider profile with all remote-worker inheritance switches
disabled. Authentication remains on the remote machine. Provider CLI arguments
from the local launcher are not forwarded; the administrator's deployed
`endpoint.json` controls the executable, arguments and fixed environment.

For example, add these fields to an existing dedicated Claude worker (replace
paths and use the exact template emitted by `configure`):

```toml
[agents.worker]
provider = "claude"
target = "."
workspace_mode = "git-worktree"
runtime_mode = "pane-backed"
restore = "auto"
permission = "manual"
remote_workspace = "worker-vps"
provider_command_template = "/path/to/venv/bin/python -I /path/to/ccb/tools/remote_provider.py --profiles /private/profiles.json --profile worker-vps {command}"

[agents.worker.provider_profile]
mode = "isolated"
inherit_api = false
inherit_auth = false
inherit_config = false
inherit_skills = false
inherit_commands = false
inherit_memory = false
```

The initial controller worktree must already exist. This is an advanced setup
interface, not an automatic migration of existing projects. Keep the worker's
normal CCB layout entry and choose this exact workspace in the profile.

`tools/remote_workspace_setup.py` implements `configure`, `deploy`, `bootstrap`,
`verify` and `rollback`. Configure an existing controller-created worktree first:

```bash
python -I tools/remote_workspace_setup.py configure --profiles /private/profiles.json \
  --profile worker-vps --project /path/project --workspace /path/project/.ccb/workspaces/worker \
  --agent worker --host worker-ssh-alias --remote-root /home/worker/.local/share/ccb-unique \
  --ssh-config /private/ssh-config --include src --include tests --include README.md
python -I tools/remote_workspace_setup.py deploy --profiles /private/profiles.json \
  --profile worker-vps --remote-claude /home/worker/.local/bin/claude
python -I tools/remote_workspace_setup.py bootstrap --profiles /private/profiles.json --profile worker-vps
```

Python 3.10+, Git, tmux and an already authenticated Claude CLI are remote
prerequisites. Fixed nonstandard Git/tmux paths and JSON argument/environment
files are supported; inspect `--help`. No SSH host-key enrollment or credential
copying is performed. The first prepare creates `repository/` and a real
`workspace/` worktree. Use a different root/identity/worktree/session for each
concurrent worker. Configuration validation precedes atomic publication.

For a source checkout, `tools/install_remote_runtime.sh` creates a local virtual
environment using the release's existing dependency manifest. It does not
replace an installed CCB or copy provider credentials. Use that environment's
Python for the tools below.

Start the independent controller with `tools/remote_ccb.py --project PROJECT
--profiles FILE -- -s`. It uses a standalone Python environment and separate
controller state. A terminal attaches normally; noninteractive startup stays
detached. Nested workflows should invoke the absolute `bin/ccb` from the same
checkout (also exposed as `CCB_PINNED_CLI`), because login shells may resolve a
globally installed older `ccb`. This entrypoint preserves managed caller identity;
do not call the outer controller launcher from a managed agent.

## Provider lifecycle

The remote Claude runs in a dedicated tmux socket/session. One SSH connection
attaches the terminal and another mirrors its exact session JSONL. CCB stores the
exact transcript path in its execution journal; it does not guess from the newest
session. Prompts explain the remote/current-worktree mapping. Request artifacts
are available through an explicit additional directory, without copying local
credentials or forwarding local hooks.

Transient SSH loss reattaches the existing session for up to the configured
deadline. Transcript resumption checks offset and SHA256 prefix before appending;
boot/generation changes during an unfinished task stop recovery. A local bridge
restart retains the unfinished generation binding. No task text is replayed.
Missing remote processes with unfinished transactions require explicit recovery.
The RPC channel retries only the identical idempotent prepare/collect/ack request.

Claude versions wrapping pasted prompts in `pasted_content` are recognized only
when the entire body matches the exact controller prompt. A unique missed wrapper
can be reread from the pinned bounded transcript on controller recovery. Quoted
markers, tool results and mismatched wrappers do not activate a task.

## Transaction contract

- `before_dispatch(job, context)` validates the pinned runtime binding, snapshots
  only allowed files, journals input and calls `prepare`. The bootstrap contains
  one commit and its current tree, not ancestor objects. The remote repository
  uses an explicit shallow boundary. Text request artifacts are length/hash
  checked and mapped to a fixed remote path. The stored CCB request stays local.
- `for_resume(job, context)` restores that mapping from the journal without
  preparing or submitting another provider task.
- `before_complete(job, decision)` runs before terminal persistence, mailbox
  completion, callback creation and release of the active agent slot. On provider
  success, it collects and validates the result, imports objects, applies files,
  then acknowledges the result. Only after this barrier can CCB report success.
- Sync failure returns `workspace_sync_failed`; non-successful provider exits
  also block the profile. New tasks cannot overtake an unfinished transaction.
- Input and result objects are pinned under
  `refs/ccb/remote-input/<workspace>/<job>` and
  `refs/ccb/remote/<workspace>/<job>`. Both peers keep durable receipts. Lost
  prepare/collect/ack responses can be recovered without repeating model work.

Default `publish="worktree"` applies files while preserving the local branch HEAD
and index. This is required by CCB WorkgroupGitIntegration: its controller creates
the reviewed commit. Remote commits remain available under a separate ref.
Excluded local files remain untouched and are not sent to the worker.

Optional `publish="commits"` advances only the dedicated worker branch and index;
it requires the whole branch tree to fit the allowlist. It is not intended for
the controller-owned workgroup commit workflow.

## Validation and recovery

Only regular file modes 100644/100755 and bounded commit/tree/blob objects are
accepted. All returned intermediate trees must fit the explicit allowlist. The
importer rejects hash mismatches, unrelated objects, non-linear history,
traversal, symlinks, hardlinks, submodules and control/credential paths. Git
configuration, hooks, indexes and `.ccb` directories are never copied. File I/O
walks directory FDs with O_NOFOLLOW. Applying a result checks the original file
contents and index/branch state; a conflicting human edit stops the transaction.
Keep other controller-side writers off the dedicated worktree during a job.
Per-file conflict checks and journaling do not make the entire filesystem update
atomic against another process racing between a check and a rename.

After confirming that the remote provider is no longer writing and the original
CCB job is terminal, use:

```bash
python tools/remote_workspace.py status --project /path/to/project --agent worker
python tools/remote_workspace.py recover --project /path/to/project --agent worker \
  --job job_xxx --provider-stopped
```

Keep the same profile environment and journal. Recovery is idempotent. It imports
results but does not rewrite a failed CCB job as completed or blindly restart a
failed chain. The operator can inspect the recovered result and start a new task.

## Maintenance and local verification

`remote_workspace_setup.py verify` checks all deployed source hashes and lists
saved versions. `deploy --update` permits code-only changes while the transaction
is acknowledged and the owned tmux worker is stopped. It locks deployment, RPC and
provider startup, checks hashes before mutation and saves the old version. A
partial deployment leaves a marker that blocks task entry. An explicit
`rollback --version HASH` restores a verified backup; it never rewinds worktrees,
transcripts or transaction history. Whole-machine crash durability still needs
platform-specific testing.

`remote_workspace.py prune --keep 20 --days 14` is a dry run. Add `--apply` after
reviewing it. Only old acknowledged payloads and their exact private Git refs are
retired. Compact receipts/tombstones, current or blocked transactions, active
transcripts, user branches and CCB history remain. No automatic timer or aggressive
Git GC is installed. SSH diagnostic logs retain a bounded tail; the active model
transcript has an explicit size cap and is never silently truncated.

Returned project tests can run with:

```bash
python -I tools/remote_verify.py --workspace /path/to/worker -- /usr/bin/python3 test_pilot.py
```

This Linux helper requires working bubblewrap and libseccomp. It creates a private
offline view, binds the worktree read-only, hides local home/Windows mounts/control
files, drops capabilities, enables NoNewPrivs and denies dangerous syscalls. Failure
never falls back to direct host execution. Wire this exact controller-owned helper
into each project's native verification command. Arbitrary reviewer shell commands
are not automatically sandboxed by the synchronization interface.

## Supported scope and limits

- Controller-originated remote worker jobs; callbacks continue locally after
  synchronization. Remote passive reply delivery and remote-originated CCB
  commands are currently unsupported.
- Explicitly configured agents in rich/hybrid v2 project configuration. Automatic
  remote profile provisioning for dynamic capacity agents or v3 workflow role
  profiles is not implemented.
- SHA-1 repositories, linear history, ordinary files including binary data and
  deletions. No merge commits, symlinks, submodules or attributes-based filters.
- 32 MiB object/expanded-file budget, 12000 objects/expanded tree entries, 128
  descendant commits, 48 MiB JSON wire budget. Deep/oversized objects fail closed.
- Per-RPC timeouts are bounded to 1–120 seconds. Completion currently holds the
  project chain lock while syncing; large repositories need streaming/incremental
  transfer and an asynchronous sync phase.
- Retention cleanup is explicit. File/directory
  type changes may fail closed. No CPU/memory resource quotas are introduced.
- Messages and imported code remain untrusted. This interface is not a sandbox
  for arbitrary local reviewer actions and does not isolate other files on the
  remote account or change central tailnet access policy.

Tests in `test/test_remote_workspace.py`, `test/test_remote_provider.py` and
`test/test_remote_deployment.py` exercise object/path attacks, conflicts,
interrupted apply, lost responses, restoration, native dispatcher callbacks and
native workgroup review/finalize/integrate/promote/accept boundaries, reconnect
identity, cancellation, bounded logs, conservative retention and code rollback.
Keep actual SSH/model acceptance evidence separately from mocked regression tests.
`test/test_remote_workspace_config.py` covers the portable configuration surface
and verifies that local-only dispatch does not import the Linux transport.
The optional verifier integration test requires working bubblewrap/libseccomp;
enable it explicitly with `CCB_TEST_REMOTE_SANDBOX=1`. It is separate from the
SSH/workspace unit tests and does not run model clients.
