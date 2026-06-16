#!/usr/bin/env python3
"""
Claude Code Pre-Tool-Use Hook — blocks destructive bash commands.

Reads a JSON tool-call envelope from stdin (Claude Code hook format).
Returns a JSON decision on stdout: {"decision": "allow"} or
{"decision": "block", "reason": "..."}.

Blocked commands are logged to ~/.claude/hooks/blocked.log.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Dangerous patterns  (all case‑insensitive)
# ---------------------------------------------------------------------------

# rm -rf variants:  rm -rf /, rm -rf *, rm -r --force /, etc.
RM_RF_PATTERN = re.compile(
    r'\brm\s+(?:-[rfv]+\s*)*?(?:--(?:recursive|force|no-preserve-root)\s+)*'
    r'(?:/\s*|\*\s*|\.\s*|~\s*|\$HOME\b)',
    re.IGNORECASE,
)

# git push --force / -f / --force-with-lease
# Note: --force starts with non-word chars, so no \b before the flags.
GIT_PUSH_FORCE_PATTERN = re.compile(
    r'\bgit\s+push\b.*?(?:--force(?:-with-lease)?|(?<=\s)-f\b)',
    re.IGNORECASE,
)

# DROP TABLE / DROP DATABASE
DROP_PATTERN = re.compile(r'\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b', re.IGNORECASE)

# TRUNCATE
TRUNCATE_PATTERN = re.compile(r'\bTRUNCATE\s+(?:TABLE\s+)?\w+', re.IGNORECASE)

# DELETE FROM without WHERE
# Finds DELETE FROM statements and checks for missing WHERE clause.
DELETE_PATTERN = re.compile(
    r'\bDELETE\s+FROM\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOG_DIR = os.path.expanduser('~/.claude/hooks')
LOG_PATH = os.path.join(LOG_DIR, 'blocked.log')


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def _log_block(command: str, reason: str, project_path: str):
    _ensure_log_dir()
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    entry = json.dumps(
        {'timestamp': timestamp, 'command': command, 'reason': reason, 'project_path': project_path},
        ensure_ascii=False,
    )
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(entry + '\n')


def _check_sql_has_where(command: str) -> bool:
    """Return True if a DELETE FROM statement includes a WHERE clause."""
    # Simple heuristic: after DELETE FROM <table>, look for WHERE
    return bool(re.search(r'\bWHERE\b', command, re.IGNORECASE))


def check_command(command: str) -> dict:
    """Return {'decision': 'block', 'reason': ...} or {'decision': 'allow'}."""
    if not command or not command.strip():
        return {'decision': 'allow'}

    # rm -rf
    if RM_RF_PATTERN.search(command):
        return {
            'decision': 'block',
            'reason': (
                'Destructive rm command detected. Use a targeted rm '
                'with explicit file paths instead of recursive/force flags.'
            ),
        }

    # git push --force variants
    if GIT_PUSH_FORCE_PATTERN.search(command):
        return {
            'decision': 'block',
            'reason': (
                'Force-push detected. Use `git push` without --force, '
                '--force-with-lease, or -f to avoid overwriting remote history.'
            ),
        }

    # DROP TABLE / DATABASE / SCHEMA
    if DROP_PATTERN.search(command):
        return {
            'decision': 'block',
            'reason': (
                'SQL DROP detected. Dropping tables, databases, or schemas '
                'is destructive and blocked by policy.'
            ),
        }

    # TRUNCATE
    if TRUNCATE_PATTERN.search(command):
        return {
            'decision': 'block',
            'reason': (
                'SQL TRUNCATE detected. Truncating tables is destructive '
                'and blocked by policy.'
            ),
        }

    # DELETE FROM without WHERE
    if DELETE_PATTERN.search(command) and not _check_sql_has_where(command):
        # Also verify it's not a harmless variation
        return {
            'decision': 'block',
            'reason': (
                'DELETE FROM without a WHERE clause detected. '
                'Unconditional table deletes are destructive and blocked by policy.'
            ),
        }

    return {'decision': 'allow'}


def main():
    try:
        raw = sys.stdin.read()
        if not raw:
            # No input — treat as allow
            print(json.dumps({'decision': 'allow'}))
            sys.exit(0)

        payload = json.loads(raw)
    except (json.JSONDecodeError, Exception) as exc:
        # If we can't parse the input, allow to avoid breaking the session
        print(json.dumps({'decision': 'allow'}))
        sys.exit(0)

    # Extract the tool name and input
    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {}) or {}
    project_path = payload.get('cwd', os.getcwd())

    # Only inspect Bash tool calls
    if tool_name.lower() not in ('bash',):
        print(json.dumps({'decision': 'allow'}))
        sys.exit(0)

    command = tool_input.get('command', '')
    if not command:
        print(json.dumps({'decision': 'allow'}))
        sys.exit(0)

    result = check_command(command)

    if result['decision'] == 'block':
        _log_block(command, result['reason'], project_path)
        print(json.dumps(result))
        # Exit code 2 signals "blocked" in Claude Code hooks
        sys.exit(2)
    else:
        print(json.dumps(result))
        sys.exit(0)


if __name__ == '__main__':
    main()
