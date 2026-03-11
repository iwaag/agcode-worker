import asyncio
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse

app = FastAPI()

WORKSPACE = "/workspace"
PID_FILE = Path("/tmp/vscode-tunnel.pid")
LOG_FILE = Path("/tmp/vscode-tunnel.log")
TUNNEL_NAME_FILE = os.environ.get("TUNNEL_NAME_FILE", "/run/secrets/tunnel-name")
TUNNEL_TIMEOUT = 30


@app.post("/hooks/on-push")
async def on_push():
    proc = await asyncio.create_subprocess_exec(
        "git", "pull",
        cwd=WORKSPACE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=stderr.decode())
    return {"status": "ok", "output": stdout.decode()}


@app.post("/hooks/start-tunnel", response_class=PlainTextResponse)
async def start_tunnel():
    # Prevent duplicate tunnel
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            return f"tunnel already running (pid={pid})"
        except ProcessLookupError:
            PID_FILE.unlink(missing_ok=True)

    # Read tunnel name
    tunnel_name_path = Path(TUNNEL_NAME_FILE)
    if not tunnel_name_path.exists():
        raise HTTPException(status_code=500, detail=f"{TUNNEL_NAME_FILE} not found")
    tunnel_name = tunnel_name_path.read_text().strip()

    # Start tunnel in background
    LOG_FILE.write_text("")
    log_fd = open(LOG_FILE, "w")
    proc = await asyncio.create_subprocess_exec(
        "code", "tunnel", "--name", tunnel_name, "--accept-server-license-terms",
        stdout=log_fd,
        stderr=log_fd,
    )
    log_fd.close()
    PID_FILE.write_text(str(proc.pid))

    # Wait for tunnel URL
    for _ in range(TUNNEL_TIMEOUT):
        await asyncio.sleep(1)
        log_content = LOG_FILE.read_text()
        match = re.search(r"https://vscode\.dev/tunnel/\S+", log_content)
        if match:
            return match.group(0)

    raise HTTPException(status_code=504, detail=f"tunnel URL not found within {TUNNEL_TIMEOUT}s")


@app.post("/hooks/sync")
async def sync():
    fetch = await asyncio.create_subprocess_exec(
        "git", "fetch", "--all",
        cwd=WORKSPACE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await fetch.communicate()

    reset = await asyncio.create_subprocess_exec(
        "git", "reset", "--hard", "origin/main",
        cwd=WORKSPACE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await reset.communicate()
    if reset.returncode != 0:
        raise HTTPException(status_code=500, detail=stderr.decode())
    return {"status": "ok", "output": stdout.decode()}
