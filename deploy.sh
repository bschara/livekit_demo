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

# LiveKit (Docker) — picks up docker-compose.yml/livekit.yaml changes
docker compose up -d

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
