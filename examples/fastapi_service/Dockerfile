# ---------- BUILD STAGE ----------
FROM python:3.11-slim AS builder

WORKDIR /install

RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    python3-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

ARG ENVIRONMENT=prod

COPY ./fastapi_service/requirements_base.txt .
COPY ./fastapi_service/requirements_dev.txt .
COPY ./fastapi_service/requirements_prod.txt .

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
ENV PYTHONPATH=/opt/fastapi_service

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /opt

COPY --from=builder /install /usr/local

COPY --chown=appuser:appuser ./fastapi_service ./fastapi_service

RUN apt-get update && apt-get install -y dos2unix && \
    rm -rf /var/lib/apt/lists/*

RUN dos2unix /opt/fastapi_service/scripts/docker_start.sh && \
    dos2unix /opt/fastapi_service/scripts/pre_start.sh && \
    chmod +x /opt/fastapi_service/scripts/*.sh

USER appuser

EXPOSE 8000

CMD ["./fastapi_service/scripts/docker_start.sh"]
