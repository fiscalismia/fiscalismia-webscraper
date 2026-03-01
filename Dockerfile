#   __      ___       __           __               __
#  |__) \ /  |  |__| /  \ |\ |    |__) |  | | |    |  \
#  |     |   |  |  | \__/ | \|    |__) \__/ | |___ |__/
# Stage 1: Pip Installation
FROM python:3.13-slim as python-base

# Accept build arguments from GitLab CI
ARG BUILD_VERSION

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

#   __      ___       __           __            ___          ___
#  |__) \ /  |  |__| /  \ |\ |    |__) |  | |\ |  |  |  |\/| |__
#  |     |   |  |  | \__/ | \|    |  \ \__/ | \|  |  |  |  | |___
# Stage 2: Final image with Nginx and Supervisor
FROM python:3.13-slim

# add non priviledged system users to run their respective services
RUN addgroup --gid 101 --system nginx && adduser --system --no-create-home --uid 101 --home /var/cache/nginx --shell /sbin/nologin --ingroup nginx nginx
RUN addgroup --gid 1001 --system python && adduser --system --no-create-home --uid 1001 --shell /sbin/nologin --ingroup python python

# Set working directory
WORKDIR /app

# Arguments have to be redefined for second stage
ARG BUILD_VERSION

# Convert build arguments to environment variables for runtime on host
ENV FASTAPI_BUILD_VERSION=$BUILD_VERSION

# Install Nginx and Supervisor
RUN apt-get update && apt-get install -y --no-install-recommends nginx supervisor && rm -rf /var/lib/apt/lists/*

# Copy Python environment from the python-base stage
COPY --from=python-base /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=python-base /usr/local/bin/ /usr/local/bin/

# Use a shared, user-agnostic path so the unprivileged python user can find the browser at runtime
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

# Install Chromium binary and its system-level dependencies
RUN playwright install chromium && \
    playwright install-deps chromium && \
    rm -rf /var/lib/apt/lists/*

# Create nginx and supervisor Directories
RUN mkdir -p /var/log/supervisor /var/log/nginx /etc/nginx/certs

# Remove default Nginx site configuration
RUN rm /etc/nginx/sites-enabled/default

# Remove default config that listens on 8080
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy Nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Change Ownership of directories according to users
RUN chown -R root:root /var/log/supervisor
RUN chown -R nginx:nginx /var/log/nginx /etc/nginx/certs/

# Copy application code
COPY main.py /app/main.py
COPY api/ /app/api/

RUN chown -R python:python /app

# Start Supervisor to manage Nginx and Uvicorn
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]