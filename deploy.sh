#!/usr/bin/env bash
# Run on the VPS by .github/workflows/ci.yml's deploy job, via SSH.
# Assumes: repo cloned at /opt/livekit-demo, backend/venv already created,
# a livekit-backend systemd unit already installed (see deploy/livekit-backend.service),
# and passwordless sudo for restarting exactly that unit.
set -euo pipefail
cd "$(dirname "$0")"

# Hard-reset rather than `git pull`: this checkout is a deploy target, not a
# place for local edits, so any local drift (e.g. a prior `npm install` here
# rewriting package-lock.json) should always lose to origin/main rather than
# blocking the next deploy.
git fetch origin main
git reset --hard origin/main

# LiveKit (Docker). `up -d` alone only recreates containers whose
# docker-compose.yml service definition changed — it can't detect edits to
# livekit.yaml, since that's just a bind-mounted file, not part of the
# service definition. Without the explicit restart, livekit-server keeps
# running on whatever config it had in memory from its last start, silently
# ignoring any livekit.yaml change in this deploy (bit us twice: once with
# a stale rtc.node_ip, once with a missing redis: block for egress).
docker compose up -d
docker compose restart livekit

# Django backend
cd backend
source venv/bin/activate
pip install -q -r requirements.txt
python manage.py migrate --noinput
deactivate
sudo systemctl restart livekit-backend
cd ..

# React frontend — nginx serves frontend/dist directly, no restart needed
cd frontend
npm ci
npm run build
cd ..

echo "Deploy complete: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
