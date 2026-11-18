"""Start the PostgreSQL MCP server for Claude Code against the local Docker database.

Reads DB_* and VIEWER_* from .env (so no password lives in .mcp.json, which is committed) and runs
`postgres-mcp` (Postgres MCP Pro) in restricted = read-only mode, as the read-only viewer_user.
stdin/stdout are passed straight through: that is the MCP stdio channel. Logs go to stderr only.

It runs the server's Docker image (not uvx): postgres-mcp needs pglast, which has no Windows build.
The container joins the compose network and reaches the database as host "db", so `docker compose up -d db`
must be running. The password goes in as an environment variable, never on the docker command line.

Standard library only, so any Python 3 works.
"""
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

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
        print(f"mcp_postgres: {env_file} not found - copy .env.example to .env", file=sys.stderr)
        return 1
    cfg = {**read_env(env_file), **{k: v for k, v in os.environ.items() if k.startswith(("DB_", "VIEWER_"))}}
    user, password = cfg["VIEWER_USER"], cfg["VIEWER_PASSWORD"]
    # Inside the compose network the database is "db" on its container port 5432 (not the host's DB_HOST/DB_PORT).
    uri = f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@db:5432/{cfg['DB_NAME']}"
    network = os.environ.get("MCP_DOCKER_NETWORK", f"{ROOT.name}_default")
    child_env = {**os.environ, "DATABASE_URI": uri}
    return subprocess.call(
        ["docker", "run", "-i", "--rm", "--network", network,
         "-e", "DATABASE_URI",                      # value taken from child_env, not shown in the command
         "crystaldba/postgres-mcp:latest", "--access-mode=restricted"],
        env=child_env)


if __name__ == "__main__":
    sys.exit(main())
