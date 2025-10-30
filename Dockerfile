# Dockerfile for KaryaKarta Agent
# Using Playwright's official Python base image (includes browsers pre-installed)

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set working directory
WORKDIR /app

# Install additional system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership to existing Playwright user (pwuser)
RUN chown -R pwuser:pwuser /app

# Switch to non-root user (pwuser exists in Playwright base image)
USER pwuser

# Expose port (Cloud Run uses PORT env var, defaults to 8080)
ENV PORT=8080
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
