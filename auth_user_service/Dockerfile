# ---------- BUILD STAGE ----------
FROM python:3.14-slim AS builder

WORKDIR /install

ARG ENVIRONMENT=production
ENV PIP_ROOT_USER_ACTION=ignore

COPY auth_user_service/requirements_base.txt .
COPY auth_user_service/requirements_dev.txt .
COPY auth_user_service/requirements_prod.txt .

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
ENV PYTHONPATH=/opt/auth_user_service

WORKDIR /opt

COPY --from=builder /install /usr/local
COPY --chown=1000:1000 ./auth_user_service ./auth_user_service

USER 1000:1000

EXPOSE 8000

CMD ["python", "/opt/auth_user_service/scripts/start.py"]
