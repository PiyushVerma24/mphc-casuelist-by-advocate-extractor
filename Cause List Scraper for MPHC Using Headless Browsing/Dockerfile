FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8000

# Install ALL Chromium/Playwright dependencies manually
# (avoids playwright install-deps which fails on newer Debian)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core browser dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    libx11-xcb1 \
    libx11-6 \
    libxcb1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrender1 \
    libxtst6 \
    libglib2.0-0 \
    libdbus-1-3 \
    libatspi2.0-0 \
    # Fonts (using correct package names for Debian Bookworm)
    fonts-liberation \
    fonts-noto-color-emoji \
    fonts-unifont \
    fontconfig \
    # Utilities
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -fv

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser ONLY (no install-deps needed)
RUN playwright install chromium

# Copy application code
COPY app.py .

# Expose the port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

# Start the application
CMD ["python", "app.py"]
