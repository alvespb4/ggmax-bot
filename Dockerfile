FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

WORKDIR /app

# Instala dependências do sistema + Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg curl unzip xvfb \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 \
    libx11-6 libx11-xcb1 libxcb1 libxext6 \
    libasound2 fonts-liberation ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Instala Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY server.py /app/server.py
COPY bot_ggmax.py /app/bot_ggmax.py
COPY index.html /app/index.html

EXPOSE 8080

CMD Xvfb :99 -screen 0 1920x1080x24 & python -u /app/server.py
