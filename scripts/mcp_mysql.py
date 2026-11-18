"""Start the MySQL MCP server for Claude Code against the local Docker database.

Reads DB_* and VIEWER_* from .env (so no password lives in .mcp.json, which is committed) and runs
the mysql_mcp_server via uvx in restricted (read-only) mode, as the read-only viewer_user.
stdin/stdout are passed straight through: that is the MCP stdio channel. Logs go to stderr only.

The mysql_mcp_server is from PyPI: https://pypi.org/project/mysql-mcp-server/

Standard library only, so any Python 3 works.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_env(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    env_file = ROOT / ".env"
    if not env_file.exists():
        print(f"mcp_mysql: {env_file} not found - copy .env.example to .env", file=sys.stderr)
        return 1
    cfg = {**read_env(env_file), **{k: v for k, v in os.environ.items() if k.startswith(("DB_", "VIEWER_"))}}

    # Inside the compose network the database is "db" on its container port 3306.
    # mysql_mcp_server expects: MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
    child_env = {
        **os.environ,
        "MYSQL_HOST": "db",  # container name in the compose network
        "MYSQL_PORT": "3306",  # container port (not host port)
        "MYSQL_USER": cfg["VIEWER_USER"],
        "MYSQL_PASSWORD": cfg["VIEWER_PASSWORD"],
        "MYSQL_DATABASE": cfg["DB_NAME"],
    }

    # Run mysql_mcp_server via uvx with restricted (read-only) mode
    # This requires 'uvx' to be installed; if not available, it will fail with a clear error.
    return subprocess.call(
        ["uvx", "mysql_mcp_server", "--read-only"],
        env=child_env)


if __name__ == "__main__":
    sys.exit(main())
