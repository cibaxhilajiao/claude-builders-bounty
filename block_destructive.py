#!/usr/bin/env python3
"""Claude Code pre-tool-use hook — blocks destructive shell commands.

Installation:
  cp block_destructive.py ~/.claude/hooks/pre-tool-use && chmod +x ~/.claude/hooks/pre-tool-use
"""

import json, os, re, sys
from datetime import datetime, timezone

# --- Blocklist: (regex, human_readable_reason) ---
BLOCKLIST = [
    (r"\brm\s+-rf\b", "rm -rf (recursive force delete)"),
    (r"\brm\s+-r\s+\/\b", "rm -r / (delete root directory)"),
    (r"\bDROP\s+TABLE\b", "DROP TABLE (database table deletion)", re.IGNORECASE),
    (r"\bTRUNCATE\s+(TABLE\s+)?\w", "TRUNCATE TABLE (wipe all rows)", re.IGNORECASE),
    (r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", "DELETE FROM without WHERE clause (bulk row deletion)", re.IGNORECASE),
    (r"\bgit\s+push\s+(--force|-f)\b", "git push --force (overwrite remote history)"),
]

LOG_PATH = os.path.expanduser("~/.claude/hooks/blocked.log")


def main():
    try:
        stdin_data = sys.stdin.read()
        hook_input = json.loads(stdin_data) if stdin_data.strip() else {}
    except json.JSONDecodeError:
        hook_input = {}

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")

    # Only intercept bash/shell tool invocations
    if tool_name not in ("bash", "Bash", "shell", "execute_command"):
        sys.exit(0)

    if not command:
        sys.exit(0)

    # Check against blocklist
    for pattern, reason, *flags in BLOCKLIST:
        flag = (flags[0] if flags else 0)
        if re.search(pattern, command, flag):
            project = os.getcwd()
            timestamp = datetime.now(timezone.utc).isoformat()

            # Log
            os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
            with open(LOG_PATH, "a") as f:
                f.write(f"[{timestamp}] BLOCKED | project={project} | pattern={pattern}\n")
                f.write(f"  command: {command[:200]}\n")

            # Message to Claude
            msg = (
                f"BLOCKED: This command was intercepted by the safety pre-tool-use hook.\n"
                f"  Reason: {reason}\n"
                f"  Command: {command[:150]}\n"
                f"  Logged to: {LOG_PATH}\n\n"
                f"  This hook protects against irreversible data loss. If you're sure\n"
                f"  this is intentional, edit or remove the hook at:\n"
                f"    ~/.claude/hooks/pre-tool-use"
            )
            print(msg, file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
