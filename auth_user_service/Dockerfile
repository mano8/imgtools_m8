# ---------- BUILD STAGE ----------
FROM dhi.io/python:3.14-dev AS builder

WORKDIR /install

# Build arg to select environment
ARG ENVIRONMENT=production
ENV PIP_ROOT_USER_ACTION=ignore

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
FROM dhi.io/python:3.14

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
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
