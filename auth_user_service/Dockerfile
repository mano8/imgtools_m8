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
ARG ENVIRONMENT=production

# Copy requirements
COPY auth_user_service/requirements_base.txt .
COPY auth_user_service/requirements_dev.txt .
COPY auth_user_service/requirements_prod.txt .

# Install dependencies into /install
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements_base.txt && \
    if [ "$ENVIRONMENT" = "development" ]; then \
        pip install --prefix=/install --no-cache-dir -r requirements_dev.txt ; \
    else \
        pip install --prefix=/install --no-cache-dir -r requirements_prod.txt ; \
    fi


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

# Fix line endings (CRLF→LF) and make scripts executable
RUN find /opt/auth_user_service/scripts -name "*.sh" -exec sed -i 's/\r$//' {} + && \
    chmod +x /opt/auth_user_service/scripts/*.sh

USER appuser

EXPOSE 8000

CMD ["./auth_user_service/scripts/docker_start.sh"]