FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências do Chromium para Debian 12 (Bookworm)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libnspr4 \
    libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 \
    libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 \
    libx11-6 libx11-xcb1 libxcb1 libxext6 \
    libasound2t64 libopus0 libvpx7 \
    fonts-liberation wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN playwright install chromium --with-deps

COPY server.py /app/server.py
COPY index.html /app/index.html

EXPOSE 8080

CMD ["python", "-u", "/app/server.py"]
