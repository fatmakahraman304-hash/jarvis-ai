#!/usr/bin/env bash
# macOS / Linux başlatıcı
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -r requirements-extra.txt
fi
[ -f .env ] || cp .env.example .env
exec .venv/bin/python run.py "$@"
