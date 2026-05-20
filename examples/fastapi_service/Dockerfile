# ---------- BUILD STAGE ----------
FROM python:3.14-slim AS builder

WORKDIR /install

ARG ENVIRONMENT=prod
ENV PIP_ROOT_USER_ACTION=ignore

COPY ./fastapi_service/requirements_base.txt .
COPY ./fastapi_service/requirements_dev.txt .
COPY ./fastapi_service/requirements_prod.txt .

RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements_base.txt && \
    if [ "$ENVIRONMENT" = "development" ]; then \
        pip install --prefix=/install --no-cache-dir -r requirements_dev.txt ; \
    else \
        pip install --prefix=/install --no-cache-dir -r requirements_prod.txt ; \
    fi


# ---------- RUNTIME STAGE ----------
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/opt/fastapi_service

WORKDIR /opt

COPY --from=builder /install /usr/local
COPY --chown=1000:1000 ./fastapi_service ./fastapi_service

USER 1000:1000

EXPOSE 8000

CMD ["python", "/opt/fastapi_service/scripts/start.py"]
