# Use Python 3.11 slim base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    # Add the local user's bin directory to PATH
    PATH="/home/appuser/.local/bin:$PATH"

# Create a non-root user and group
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

# Set working directory
WORKDIR /opt

# Install build dependencies if needed (e.g., for any compiled packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    dos2unix \
    default-mysql-client \
    python3-dev \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create the app directories and set permissions
RUN mkdir -p ./auth_user_service ./common \
    && chown -R appuser:appuser ./auth_user_service ./common

# Copy requirements and install them as the non-root user
COPY --chown=appuser:appuser ./auth_user_service/requirements-docker-dev.txt .

# Switch to the non-root user
USER appuser

# Install Python dependencies
# Use --no-cache-dir to avoid caching the packages in the image
# Use --user to install packages in the user's home directory
RUN pip install --no-cache-dir --user --upgrade pip && \
    pip install --no-cache-dir --user -r requirements-docker-dev.txt

# Copy the auth_user_service source code
COPY --chown=appuser:appuser ./auth_user_service ./auth_user_service
COPY --chown=appuser:appuser ./common ./common

RUN dos2unix /opt/auth_user_service/scripts/docker_start.sh
RUN dos2unix /opt/auth_user_service/scripts/pre_start.sh

# Ensure scripts have execution permission
RUN chmod +x /opt/auth_user_service/scripts/docker_start.sh \
    && chmod +x /opt/auth_user_service/scripts/pre_start.sh

# Set the PYTHONPATH to ensure the auth_user_service module is found
ENV PYTHONPATH=/opt/auth_user_service
ENV PYTHONPATH=/opt/common

# Expose FastAPI port (use 8000)
EXPOSE 8000

# Use the entrypoint script as CMD, which will run migrations and then launch uvicorn
CMD ["./auth_user_service/scripts/docker_start.sh"]