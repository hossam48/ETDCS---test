# =============================================================================
# Dockerfile - ETDCS (Elsewedy Technical Document Control System)
# Task 14 - Docker Deployment
# =============================================================================
# Multi-stage not needed for Streamlit - single stage is simpler
# Non-root user for security
# Health check for container orchestration
# =============================================================================

FROM python:3.11-slim

# -----------------------------------------------------------------------------
# Metadata
# -----------------------------------------------------------------------------
LABEL maintainer="Elsewedy PSP - MEP Design Team"
LABEL version="1.0"
LABEL description="ETDCS - Technical Document Control System"

# -----------------------------------------------------------------------------
# Working Directory
# -----------------------------------------------------------------------------
WORKDIR /app

# -----------------------------------------------------------------------------
# System Dependencies
# -----------------------------------------------------------------------------
# fonts-noto: Arabic font support for PDF generation
# fonts-noto-extra: Extended font coverage
# curl: Required for health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto \
    fonts-noto-extra \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# -----------------------------------------------------------------------------
# Python Dependencies
# -----------------------------------------------------------------------------
# Copy requirements first for better layer caching
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Application Code
# -----------------------------------------------------------------------------
# Copy all application files
COPY . .

# -----------------------------------------------------------------------------
# Directory Structure
# -----------------------------------------------------------------------------
# Create required directories for data persistence
RUN mkdir -p database \
             files \
             uploads/quarantine \
             files/reports

# -----------------------------------------------------------------------------
# Security: Non-root User
# -----------------------------------------------------------------------------
# Create appuser with UID 1000
# This prevents running as root inside the container
RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

# -----------------------------------------------------------------------------
# Network Configuration
# -----------------------------------------------------------------------------
EXPOSE 8501

# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
# Streamlit provides /_stcore/health endpoint
# Checks every 30s, times out after 10s
# Allows 5s startup grace period, 3 retries before unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
# Run Streamlit in headless mode for container environment
CMD ["streamlit", "run", "main_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
