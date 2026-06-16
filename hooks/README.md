# Pre‑Tool‑Use Hook: Block Destructive Bash Commands

A [Claude Code](https://code.claude.com) `PreToolUse` hook that blocks destructive shell commands before they execute.

## 🚫 What It Blocks

| Pattern | Example |
|---|---|
| `rm -rf` (and variants) | `rm -rf /`, `rm -rf *`, `rm -r --force $HOME` |
| `git push --force` / `-f` | `git push origin main --force`, `git push -f` |
| SQL `DROP TABLE` / `DROP DATABASE` | `DROP TABLE users;` |
| SQL `TRUNCATE` | `TRUNCATE users;` |
| SQL `DELETE FROM` without `WHERE` | `DELETE FROM users;` |

## ✅ Commands That Pass Through

All safe commands — `rm file.txt`, `git push`, `SELECT`, `DELETE FROM ... WHERE id = 1` — are allowed without interruption.

## Install

```sh
curl -o ~/.claude/hooks/pre-tool-use-hook.py https://raw.githubusercontent.com/cibaxhilajiao/claude-builders-bounty/main/hooks/pre-tool-use-hook.py
chmod +x ~/.claude/hooks/pre-tool-use-hook.py
```

Then add to `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": "python3 ~/.claude/hooks/pre-tool-use-hook.py"
  }
}
```

Done — the hook is active on your next Claude Code session.

## How It Works

1. Claude Code sends a JSON tool-call envelope to the hook via stdin.
2. The hook checks whether the tool is `Bash` and evaluates the command.
3. **Safe commands** → exits 0 with `{"decision": "allow"}`.
4. **Dangerous commands** → logs the attempt to `~/.claude/hooks/blocked.log`, prints `{"decision": "block", "reason": "..."}`, and exits 2 (Claude Code's block signal).

## Logs

Blocked attempts are recorded in `~/.claude/hooks/blocked.log` as JSON lines:

```json
{"timestamp": "2026-06-16T12:00:00Z", "command": "rm -rf /", "reason": "Destructive rm command detected...", "project_path": "/home/user/my-project"}
```

## License

MIT
