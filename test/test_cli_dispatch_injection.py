from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import subprocess

import pytest

from cli import entrypoint_runtime, phase2
from cli.phase2_runtime import handlers_start
from terminal_runtime import api


@pytest.mark.parametrize('override', [False, True])
def test_entrypoint_preserves_early_commands_and_selects_one_handler(monkeypatch, tmp_path, override):
    calls = []
    monkeypatch.setattr(entrypoint_runtime, 'maybe_handle_phase2',
                        lambda *a, **kw: calls.append('default') or 7)
    handler = (lambda *a, **kw: calls.append('custom') or 9) if override else None
    kwargs = dict(version='test', script_root=tmp_path, cwd=tmp_path,
                  stdout=StringIO(), stderr=StringIO(), phase2_handler=handler)
    assert entrypoint_runtime.run_cli_entrypoint(['--print-version'], **kwargs) == 0
    assert not calls
    assert entrypoint_runtime.run_cli_entrypoint(['config', 'validate'], **kwargs) == (9 if override else 7)
    assert calls == ['custom' if override else 'default']


@pytest.mark.parametrize('override', [False, True])
def test_dispatch_runs_after_context_and_bootstrap(monkeypatch, tmp_path, override):
    events = []
    context = SimpleNamespace(project=SimpleNamespace(project_root=tmp_path))
    monkeypatch.setattr(phase2, '_build_context', lambda *a, **kw: events.append('context') or context)
    monkeypatch.setattr(phase2, 'ensure_bootstrap_project_config', lambda root: events.append('bootstrap'))
    monkeypatch.setattr(phase2, '_dispatch', lambda *a: events.append('default') or 7)
    def custom(ctx, cmd, out):
        assert ctx is context and cmd.kind == 'start'
        events.append('custom')
        return 9
    assert phase2.maybe_handle_phase2([], cwd=tmp_path, stdout=StringIO(), stderr=StringIO(),
                                     dispatch_fn=custom if override else None) == (9 if override else 7)
    assert events == ['context', 'bootstrap', 'custom' if override else 'default']


def test_dispatch_errors_keep_standard_reporting(monkeypatch, tmp_path):
    monkeypatch.setattr(phase2, '_build_context', lambda *a, **kw: object())
    def fail(*args):
        raise RuntimeError('custom dispatch unavailable')
    err = StringIO()
    assert phase2.maybe_handle_phase2(['config', 'validate'], cwd=tmp_path, stdout=StringIO(),
                                     stderr=err, dispatch_fn=fail) == 1
    assert 'custom dispatch unavailable' in err.getvalue()


@pytest.mark.parametrize('interactive', [False, True])
def test_start_attach_injection_preserves_headless_and_start_order(monkeypatch, interactive):
    events = []
    monkeypatch.delenv('CCB_NO_ATTACH', raising=False)
    monkeypatch.setattr(handlers_start, '_ensure_project_commands_approved', lambda *a: None)
    monkeypatch.setattr(handlers_start, '_ensure_herdr_runtime_evidence', lambda *a: None)
    monkeypatch.setattr(handlers_start, '_stream_is_tty', lambda stream: interactive)
    monkeypatch.setattr(handlers_start, '_terminal_size_for_streams', lambda *a: (80, 24))
    services = SimpleNamespace(start_agents=lambda *a, **kw: events.append('start'),
                               render_start=lambda summary: [], write_lines=lambda *a: None)
    assert handlers_start.handle_start(object(), object(), StringIO(), services,
                                        attach_fn=lambda ctx: events.append('attach')) == 0
    assert events == (['start', 'attach'] if interactive else ['start'])


@pytest.mark.parametrize('explicit', [False, True])
def test_process_wrapper_preserves_explicit_options_and_default_fallback(monkeypatch, explicit):
    calls = []
    monkeypatch.setattr(api, '_subprocess_kwargs', lambda: {'creationflags': 123})
    monkeypatch.setattr(subprocess, 'run', lambda *a, **kw: calls.append(kw) or subprocess.CompletedProcess(a, 0))
    api._run(['test-only'], **({'creationflags': 0} if explicit else {}))
    assert calls[0]['creationflags'] == (0 if explicit else 123)


def test_root_injection_does_not_bypass_source_guard(monkeypatch, tmp_path):
    monkeypatch.setattr('stdio_runtime.setup_windows_encoding', lambda: None)
    monkeypatch.setenv('CCB_SKIP_HERDR_CHECK', '1')
    spec = importlib.util.spec_from_file_location('ccb_injection_test', Path(__file__).resolve().parents[1] / 'ccb.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    monkeypatch.setattr(module, '_source_runtime_allowed', lambda *a: (False, 'source blocked'))
    assert module.main(entrypoint=lambda *a, **kw: calls.append(kw) or 0) == 1
    assert not calls
    monkeypatch.setattr(module, '_source_runtime_allowed', lambda *a: (True, ''))
    monkeypatch.setattr(module, '_herdr_ok', True)
    assert module.main(entrypoint=lambda *a, **kw: calls.append(kw) or 13) == 13
    assert len(calls) == 1 and calls[0]['script_root'] == module.script_dir
