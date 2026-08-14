# RankPilot AI — API + Redis + ARQ worker in one container.
# Designed for a Hugging Face Docker Space (serves on port 7860).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System deps: redis-server (bundles redis-cli), plus build tooling as a
# fallback for any dependency without a prebuilt wheel.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      redis-server curl build-essential \
 && rm -rf /var/lib/apt/lists/*

# HF Spaces run the container as uid 1000 — create a matching user.
RUN useradd -m -u 1000 user

WORKDIR /app

# Install Python deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App source.
COPY . .

# Writable dirs + normalize the start script (strip any CRLF, make executable).
RUN mkdir -p /home/user/redis \
 && sed -i 's/\r$//' start.sh \
 && chmod +x start.sh \
 && chown -R user:user /app /home/user

USER user
ENV HOME=/home/user \
    HOST=0.0.0.0 \
    PORT=7860 \
    REDIS_URL=redis://127.0.0.1:6379

EXPOSE 7860

CMD ["bash", "start.sh"]
