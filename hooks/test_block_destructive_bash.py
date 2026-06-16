#!/usr/bin/env python3
"""Tests for the destructive bash command block hook."""

import json
import subprocess
import sys
from pathlib import Path

HOOK_PATH = Path(__file__).parent.parent / "hooks" / "block-destructive-bash.py"


def make_bash_tool(command: str) -> str:
    """Create valid JSON for a Bash tool call with given command."""
    return json.dumps({
        "tool": "Bash",
        "tool_input": {"command": command},
        "cwd": "/home/user",
        "hook_event": "pre_tool_use",
    })

OTHER_TOOL = json.dumps({
    "tool": "Read",
    "tool_input": {"file_path": "test.txt"},
    "hook_event": "pre_tool_use",
})

def run_hook(stdin: str) -> dict:
    """Run the hook with given stdin JSON and return parsed response."""
    proc = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        input=stdin,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout.strip() or "{}")


def test_block_rm_rf_root():
    """rm -rf / should be blocked."""
    result = run_hook(make_bash_tool("rm -rf /"))
    assert result["continue"] is False, f"Expected block, got {result}"
    assert "filesystem" in result["reason"].lower()

def test_block_rm_rf_etc():
    """rm -rf /etc should be blocked."""
    result = run_hook(make_bash_tool("rm -rf /etc/nginx"))
    assert result["continue"] is False

def test_block_rm_rf_var():
    """rm -rf /var should be blocked."""
    result = run_hook(make_bash_tool("rm -rf /var/log"))
    assert result["continue"] is False

def test_allow_rm_normal_file():
    """rm somefile.txt should be allowed."""
    result = run_hook(make_bash_tool("rm somefile.txt"))
    assert result["continue"] is True

def test_allow_rm_rf_project_dir():
    """rm -rf ./node_modules should be allowed (not system path)."""
    result = run_hook(make_bash_tool("rm -rf ./node_modules"))
    assert result["continue"] is True

def test_block_dd_to_disk():
    """dd writing to raw disk should be blocked."""
    result = run_hook(make_bash_tool("dd if=/dev/zero of=/dev/sda bs=1M"))
    assert result["continue"] is False

def test_block_mkfs():
    """mkfs should be blocked."""
    result = run_hook(make_bash_tool("mkfs.ext4 /dev/sdb1"))
    assert result["continue"] is False

def test_block_wipefs():
    """wipefs should be blocked."""
    result = run_hook(make_bash_tool("wipefs /dev/sda"))
    assert result["continue"] is False

def test_block_shred_dev():
    """shred on /dev should be blocked."""
    result = run_hook(make_bash_tool("shred -f /dev/sda"))
    assert result["continue"] is False

def test_block_fork_bomb():
    """Classic fork bomb should be blocked."""
    result = run_hook(make_bash_tool(":(){ :|:& };:"))
    assert result["continue"] is False
    assert "fork bomb" in result["reason"].lower()

def test_block_python_fork_bomb():
    """Python fork bomb should be blocked."""
    result = run_hook(make_bash_tool('python3 -c "while True: os.fork()"'))
    assert result["continue"] is False

def test_warn_pip_install():
    """pip install should trigger warning but allow."""
    result = run_hook(make_bash_tool("pip install requests"))
    assert result["continue"] is True
    assert "warning" in result

def test_warn_git_push_force():
    """git push --force should warn."""
    result = run_hook(make_bash_tool("git push --force origin main"))
    assert result["continue"] is True
    assert "warning" in result

def test_allow_empty_command():
    """Empty or None command should be allowed."""
    result = run_hook(json.dumps({"tool":"Bash","tool_input":{}}))
    assert result["continue"] is True

def test_allow_non_bash_tool():
    """Non-Bash tools should pass through."""
    result = run_hook(OTHER_TOOL)
    assert result["continue"] is True

def test_allow_normal_commands():
    """Normal dev commands should all pass."""
    normal = [
        "ls -la",
        "git status",
        "npm install express",
        "mkdir -p /tmp/build",
        "cat package.json",
        "echo hello world",
        "curl https://api.example.com",
        "docker ps",
        "grep -r 'pattern' ./src",
        "find . -name '*.py'",
    ]
    for cmd in normal:
        result = run_hook(make_bash_tool(cmd))
        assert result["continue"] is True, f"Should allow: {cmd}"

def test_block_sudo_rm():
    """sudo rm -rf / should be blocked."""
    result = run_hook(make_bash_tool("sudo rm -rf /"))
    assert result["continue"] is False

def test_block_chmod_777_root():
    """chmod 777 on root should be blocked."""
    result = run_hook(make_bash_tool("sudo chmod -R 777 /"))
    assert result["continue"] is False

def test_allow_chmod_non_root():
    """chmod 777 on non-root dir should be allowed."""
    result = run_hook(make_bash_tool("chmod 777 ./my-project"))
    assert result["continue"] is True


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            print(f"  PASS: {test_fn.__doc__ or test_fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test_fn.__doc__ or test_fn.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {test_fn.__doc__ or test_fn.__name__} — {e}")
            failed += 1

    print(f"\n{passed + failed} tests: {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
