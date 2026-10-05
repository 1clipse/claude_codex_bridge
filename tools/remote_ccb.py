#!/usr/bin/env python3
"""Run the pinned CCB source with an explicit project and trusted profiles."""

import argparse
import hashlib
import os
import pwd
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--profiles', required=True, type=Path)
    parser.add_argument('--state', type=Path)
    parser.add_argument(
        '--provider-source-home', type=Path, default=Path(pwd.getpwuid(os.getuid()).pw_dir)
    )
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    project, profiles = args.project.resolve(), args.profiles.resolve()
    source = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source / 'lib'))
    from remote_workspace.files import read_json
    from remote_workspace.provider_client import load_profile

    configured = read_json(profiles)
    matching = [name for name, p in configured.items() if p['project_root'] == str(project)]
    if not matching:
        parser.error('project is not registered in trusted profiles')
    for name in matching:
        load_profile(profiles, name)
    state = (
        args.state
        or profiles.parent
        / ('controller-' + hashlib.sha256(str(project).encode()).hexdigest()[:12])
    ).resolve()
    if state.is_relative_to(project):
        parser.error('controller state must be outside the project')
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(('CCB_', 'CLAUDE_', 'ANTHROPIC_'))
        and k not in ('CODEX_HOME', 'CODEX_SESSION_ROOT', 'TMUX', 'TMUX_PANE')
    }
    env.update(
        CCB_SOURCE_HOME=str(state / 'home'),
        XDG_STATE_HOME=str(state / 'state'),
        CCB_PROVIDER_SOURCE_HOME=str(args.provider_source_home.resolve()),
        XDG_CACHE_HOME=str(state / 'cache'),
        CCB_PYTHON=sys.executable,
        CCB_PYTHON_CACHE=str(state / 'python-bin'),
        CCB_SOURCE_ALLOWED_ROOTS=str(project),
        CCB_REMOTE_WORKSPACES_FILE=str(profiles),
        CCB_NO_UPDATE_CHECK='1',
    )
    if not sys.stdin.isatty():
        env['CCB_NO_ATTACH'] = '1'
    argv = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    os.chdir(project)
    entry = source / 'ccb.py'
    if argv[:1] == ['sync']:
        entry = source / 'tools/remote_workspace.py'
        argv = [*argv[1:], '--project', str(project)]
        if '--agent' not in argv:
            if len(matching) != 1:
                parser.error('sync requires --agent when the project has multiple remote profiles')
            argv += ['--agent', configured[matching[0]]['agent_name']]
    os.execve(sys.executable, [sys.executable, '-I', str(entry), *argv], env)


if __name__ == '__main__':
    main()
