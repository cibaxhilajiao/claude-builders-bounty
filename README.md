# Claude Code Safety Hook — Block Destructive Commands

Pre-tool-use hook that intercepts dangerous bash commands before execution.

## Blocked Patterns

| Pattern | Risk |
|---------|------|
| `rm -rf` / `rm -r /` | Irreversible file deletion |
| `DROP TABLE` | Database table destruction |
| `TRUNCATE TABLE` | All-row wipe without backup |
| `DELETE FROM` (without WHERE) | Bulk row deletion |
| `git push --force` / `-f` | Overwritten remote history |

## Quick Install

```bash
# 1. Download
curl -sL https://raw.githubusercontent.com/cibaxhilajiao/claude-builders-bounty/hook/block-destructive-commands-3/block_destructive.py -o ~/.claude/hooks/pre-tool-use

# 2. Make executable
chmod +x ~/.claude/hooks/pre-tool-use
```

## How It Works

Claude Code calls this hook before every bash tool invocation. The hook:

1. Reads JSON input from stdin (Claude Code hook protocol)
2. Checks the command against blocklist patterns
3. If blocked → logs to `~/.claude/hooks/blocked.log`, prints reason to stderr, exits with code 2
4. If safe → exits 0 (Claude proceeds)

## Log Format

```
[2026-06-16T02:17:04+00:00] BLOCKED | project=/home/user/project | pattern=\brm\s+-rf\b
  command: rm -rf /important/dir
```

## Disable

```bash
rm ~/.claude/hooks/pre-tool-use
```

## Testing

```bash
# Should block (exit 2)
echo '{"tool_name":"bash","tool_input":{"command":"rm -rf /tmp"}}' | python3 ~/.claude/hooks/pre-tool-use

# Should pass (exit 0)
echo '{"tool_name":"bash","tool_input":{"command":"ls -la"}}' | python3 ~/.claude/hooks/pre-tool-use
```
