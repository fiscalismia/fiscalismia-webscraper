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
COPY ./.pip/pip.conf ~/.pip/pip.conf
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# if SSL Certificate errors persist use proxy and trusted-host
# RUN pip install --no-cache-dir --upgrade pip --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org
# RUN pip install --no-cache-dir -r requirements.txt --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org

#   __      ___       __           __            ___          ___
#  |__) \ /  |  |__| /  \ |\ |    |__) |  | |\ |  |  |  |\/| |__
#  |     |   |  |  | \__/ | \|    |  \ \__/ | \|  |  |  |  | |___
# Stage 2: Final image with Nginx and Supervisor
FROM gdis-docker-virtual.artifact-repository.generali-gruppe.de/python:3.13-slim

# Arguments have to be redefined for second stage
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG BUILD_VERSION

# Convert build arguments to environment variables for runtime on host
ENV FASTAPI_BUILD_VERSION=$BUILD_VERSION

# Install Nginx and Supervisor
RUN apt-get update && apt-get install -y --no-install-recommends nginx supervisor && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python environment from the python-base stage
COPY --from=python-base /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=python-base /usr/local/bin/ /usr/local/bin/

# Copy Nginx configuration
# Remove default Nginx site configuration
RUN rm /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/nginx.conf

# Copy Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy application code
COPY main.py .
COPY app/ ./app/

# Start Supervisor to manage Nginx and Uvicorn
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]