#!/bin/bash
set -e

GITHUB_TOKEN_FILE="${GITHUB_TOKEN_FILE:-/run/secrets/github-token}"
VSCODE_TOKEN_FILE="${VSCODE_TOKEN_FILE:-/run/secrets/vscode-token}"
GIT_HOST_FILE="${GIT_HOST_FILE:-/run/secrets/git-host}"

# Git HTTPS credential setup
if [ -f "$GITHUB_TOKEN_FILE" ]; then
    GITHUB_TOKEN=$(cat "$GITHUB_TOKEN_FILE")
    GIT_HOST="github.com"
    if [ -f "$GIT_HOST_FILE" ]; then
        GIT_HOST=$(cat "$GIT_HOST_FILE" | tr -d '[:space:]')
    fi
    git config --global credential.helper store
    echo "https://x-token-auth:${GITHUB_TOKEN}@${GIT_HOST}" > ~/.git-credentials
    chmod 600 ~/.git-credentials
    echo "[entrypoint] git HTTPS credential configured (host=$GIT_HOST)"
else
    echo "[entrypoint] WARNING: $GITHUB_TOKEN_FILE not found, git auth skipped"
fi

# VS Code tunnel login
if [ -f "$VSCODE_TOKEN_FILE" ]; then
    VSCODE_TOKEN=$(cat "$VSCODE_TOKEN_FILE")
    code tunnel user login --provider github --access-token "$VSCODE_TOKEN"
    echo "[entrypoint] VS Code tunnel login done"
else
    echo "[entrypoint] WARNING: $VSCODE_TOKEN_FILE not found, tunnel login skipped"
fi

# Start FastAPI server
exec uvicorn main:app --app-dir /app --host 0.0.0.0 --port 9000
