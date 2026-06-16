#!/usr/bin/env python3
"""
Pre-tool-use hook for Claude Code that blocks destructive bash commands.

Place this in ~/.claude/hooks/ or project-level .claude/hooks/

Claude Code invokes this with JSON on stdin:
  {"tool":"Bash","tool_input":{"command":"..."},"cwd":"...","hook_event":"pre_tool_use",...}

The hook returns JSON on stdout:
  {"continue": true}  — allow the command
  {"continue": false, "reason": "..."} — block with explanation

If the hook exits non-zero, Claude will block the command by default.
"""

import json
import re
import sys


# Patterns that are always blocked (cannot be overridden)
BLOCK_PATTERNS: list[tuple[str, str]] = [
    # Filesystem destruction
    (r"\brm\s+-rf\s+/(\s|$)", "rm -rf / — total filesystem wipe blocked"),
    (r"\brm\s+-rf\s+\/(etc|boot|bin|sbin|lib|lib64|usr|var|home)\b", "rm -rf on system directory blocked"),
    (r"\brm\s+-rf\s+\*\s*$", "rm -rf * — wildcard root wipe suspicious"),
    # Disk destruction
    (r"\bdd\s+if=.*\s+of=/dev/[a-z]+", "dd writing to raw disk device blocked"),
    (r"\bmkfs\.", "mkfs (filesystem creation/format) blocked"),
    (r"\bwipefs\b", "wipefs (wipe filesystem signatures) blocked"),
    (r"\bshred\s+.*\/dev\/", "shred on dev device blocked"),
    # Fork bombs
    (r":\(\)\s*\{.*:\|:.*\}", "fork bomb pattern blocked"),
    (r"\bperl\s+-e\s+.*fork", "perl fork bomb blocked"),
    (r"python.*os\.fork", "Python fork bomb (os.fork) blocked"),
    # Dangerous redirects
    (r">\s*/dev/sda", "redirect to raw disk blocked"),
    (r"sudo\s+rm\s+-rf\s+/", "sudo rm -rf / blocked"),
    (r"sudo\s+chmod\s+(-R\s+)?777\s+/", "chmod 777 on root blocked"),
]

# Patterns that trigger a warning but can be allowed with explicit confirmation
# (These are flagged but the hook doesn't block — Claude asks for confirmation)
WARN_PATTERNS: list[tuple[str, str]] = [
    (r"\bpip\s+(?:un)?install\b", "pip install/uninstall detected — verify target"),
    (r"\bnpm\s+(?:un)?install\s+-g\b", "npm global install/uninstall detected"),
    (r"\bgpg\s+--delete-secret-key\b", "gpg secret key deletion flagged"),
    (r"\bgit\s+(?:push|pull)\s+--force\b", "git force push/pull flagged"),
    (r"\b:wq!\b", "vim force quit — check for unintended overwrites (unlikely in script)"),
]


def evaluate_command(command: str) -> dict:
    """Evaluate a bash command and return block/warn/allow decision."""
    if not command or not isinstance(command, str):
        return {"continue": True}

    # Check fatal patterns first
    for pattern, reason in BLOCK_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return {"continue": False, "reason": reason, "matched_pattern": pattern}

    # Check warning patterns
    for pattern, reason in WARN_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return {
                "continue": True,
                "warning": reason,
                "matched_pattern": pattern,
            }

    return {"continue": True}


def main():
    try:
        raw = sys.stdin.read()
        if not raw:
            print(json.dumps({"continue": True}))
            return

        tool_call = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        # If we can't parse input, default to allowing (fail-open is less disruptive)
        print(json.dumps({"continue": True}))
        return

    # Only handle Bash tool calls
    if tool_call.get("tool") != "Bash":
        print(json.dumps({"continue": True}))
        return

    # Extract the command
    tool_input = tool_call.get("tool_input", {})
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else str(tool_input)

    result = evaluate_command(command)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
