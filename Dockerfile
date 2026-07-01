FROM python:3.10-slim

WORKDIR /app

# Install system deps including git (required for git+ pip installs) and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir keeps image lean; git deps need git installed above
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
