from pathlib import Path
import json
import shutil
import subprocess

import pytest

PS = shutil.which('powershell')
pytestmark = pytest.mark.skipif(not PS, reason='Windows PowerShell 5.1 required')
HELPER = Path(__file__).resolve().parents[1] / 'platforms/windows/installer/config_io.ps1'


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def run(tmp_path, path, body):
    script = tmp_path / 'exercise.ps1'
    script.write_text("$ErrorActionPreference='Stop'\n. " + literal(HELPER) +
                      '\n$target = ' + literal(path) + '\n' + body, encoding='utf-8-sig')
    return subprocess.run([PS, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                           '-File', str(script)], capture_output=True, timeout=30)


def test_chinese_deep_configuration_and_exact_backup(tmp_path):
    path = tmp_path / '中文配置.json'
    nested = {'value': '项目😀'}
    for _ in range(20):
        nested = {'nested': nested}
    original = {'hooks': nested, 'permissions': {'allow': ['Read'], 'deny': ['Write']}}
    raw = json.dumps(original, ensure_ascii=False).encode('utf-8')
    path.write_bytes(raw)
    result = run(tmp_path, path, "$value=Read-CCBSettings $target\n$value.permissions.allow += 'Bash(ccb ask *)'\nWrite-CCBSettings $target $value")
    assert result.returncode == 0, result.stderr
    actual = json.loads(path.read_bytes())
    assert actual['hooks'] == original['hooks']
    assert actual['permissions']['deny'] == ['Write']
    assert not path.read_bytes().startswith(b'\xef\xbb\xbf')
    assert list(tmp_path.glob('*.ccb-backup-*'))[0].read_bytes() == raw


@pytest.mark.parametrize('raw', [b'{broken', b'null', b'[]', b'', b'\xff',
                                  b'{"permissions":"bad"}', b'{"permissions":{"allow":"bad"}}'])
def test_bad_configuration_fails_without_writing(tmp_path, raw):
    path = tmp_path / 'settings.json'
    path.write_bytes(raw)
    result = run(tmp_path, path, '$value=Read-CCBSettings $target\nWrite-CCBSettings $target $value')
    assert result.returncode != 0
    assert path.read_bytes() == raw
    assert not list(tmp_path.glob('*.ccb-backup-*'))


def test_concurrent_change_is_preserved(tmp_path):
    path = tmp_path / 'settings.json'
    path.write_text('{}')
    result = run(tmp_path, path, "$value=Read-CCBSettings $target\n[IO.File]::WriteAllText($target, '{\"edited\":true}')\nWrite-CCBSettings $target $value")
    assert result.returncode != 0
    assert json.loads(path.read_bytes()) == {'edited': True}


def test_new_file_and_bom_input(tmp_path):
    path = tmp_path / 'settings.json'
    for raw in [None, b'\xef\xbb\xbf{}']:
        if raw is not None:
            path.write_bytes(raw)
        result = run(tmp_path, path, '$value=Read-CCBSettings $target\nWrite-CCBSettings $target $value')
        assert result.returncode == 0, result.stderr
        assert json.loads(path.read_bytes()) == {}
        assert not path.read_bytes().startswith(b'\xef\xbb\xbf')
