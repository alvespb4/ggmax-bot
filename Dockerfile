FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema para o Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Playwright e Chromium
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiar código
COPY . .

# Iniciar servidor
CMD ["python", "server.py"]
