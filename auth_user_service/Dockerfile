# ---------- BUILD STAGE ----------
FROM python:3.11-slim AS builder

WORKDIR /install

# System deps for building wheels (only here, not in final image)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Build arg to select environment
ARG ENVIRONMENT=prod

# Copy requirements
COPY requirements_base.txt .
COPY requirements_dev.txt .
COPY requirements_prod.txt .

# Install dependencies into /install
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements_${ENVIRONMENT}.txt


# ---------- RUNTIME STAGE ----------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PATH="/home/appuser/.local/bin:$PATH"
ENV PYTHONPATH=/opt/auth_user_service

# Create non-root user
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /opt

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy app code
COPY --chown=appuser:appuser ./auth_user_service ./auth_user_service

# Minimal runtime tools
RUN apt-get update && apt-get install -y dos2unix && \
    rm -rf /var/lib/apt/lists/*

# Fix scripts
RUN dos2unix /opt/auth_user_service/scripts/docker_start.sh && \
    dos2unix /opt/auth_user_service/scripts/pre_start.sh && \
    chmod +x /opt/auth_user_service/scripts/*.sh

USER appuser

EXPOSE 8000

CMD ["./auth_user_service/scripts/docker_start.sh"]