# ---------- BUILD STAGE ----------
FROM dhi.io/python:3.14-dev AS builder

WORKDIR /install

ARG ENVIRONMENT=prod
ENV PIP_ROOT_USER_ACTION=ignore

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
FROM dhi.io/python:3.14

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/home/appuser/.local/bin:$PATH"
ENV PYTHONPATH=/opt/fastapi_service

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /opt

COPY --from=builder /install /usr/local

COPY --chown=appuser:appuser ./fastapi_service ./fastapi_service

# Fix line endings (CRLF→LF) and make scripts executable
RUN find /opt/fastapi_service/scripts -name "*.sh" -exec sed -i 's/\r$//' {} + && \
    chmod +x /opt/fastapi_service/scripts/*.sh

USER appuser

EXPOSE 8000

CMD ["./fastapi_service/scripts/docker_start.sh"]
