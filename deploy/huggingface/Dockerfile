# DermAI API - imagen para Hugging Face Spaces (SDK Docker, CPU gratuita).
# Se construye desde la carpeta que genera scripts/build-space.ps1 (deploy/huggingface/build).

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Hugging Face Spaces ejecuta el contenedor con el usuario de UID 1000.
RUN useradd --create-home --uid 1000 user
WORKDIR /app

# Dependencias primero (capa reutilizable). PyTorch en su versión solo para CPU (más ligera).
COPY backend/requirements.txt /tmp/requirements-backend.txt
COPY ai/requirements.txt /tmp/requirements-ai.txt
RUN pip install -r /tmp/requirements-backend.txt \
    && pip install --index-url https://download.pytorch.org/whl/cpu -r /tmp/requirements-ai.txt

COPY --chown=user:user backend /app/backend
COPY --chown=user:user ai /app/ai
COPY --chown=user:user model /app/model
COPY --chown=user:user start.sh /app/start.sh

# Configuración de la demo pública. Los datos viven en /tmp: se borran en cada reinicio del Space.
ENV APP_ENV=production \
    LOG_LEVEL=INFO \
    DEMO_MODE=true \
    DEMO_RETENTION_HOURS=6 \
    DEMO_RATE_LIMIT_PER_HOUR=30 \
    DATABASE_URL=sqlite:////tmp/dermai/dermai.db \
    STORAGE_PATH=/tmp/dermai/storage \
    AI_DEVICE=cpu \
    CORS_ORIGINS=https://wilmer-fp.github.io \
    FRONTEND_URL=https://wilmer-fp.github.io/dermai/ \
    TORCH_HOME=/tmp/torch \
    OMP_NUM_THREADS=2

USER user
EXPOSE 7860
CMD ["sh", "/app/start.sh"]
