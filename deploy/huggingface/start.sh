#!/bin/sh
# Arranque de la demo: base de datos SQLite efímera, modelo registrado y API en el puerto 7860.
set -e

mkdir -p /tmp/dermai/storage
cd /app/backend

python -m alembic upgrade head
python -m app.cli register-model /app/model --activate --if-missing

# --proxy-headers: Hugging Face está detrás de un proxy; así el límite por IP usa la IP real.
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}" \
    --proxy-headers --forwarded-allow-ips="*"
