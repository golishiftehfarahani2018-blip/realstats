FROM node:24.22.1-bookworm-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12.14-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends nginx libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=web /usr/local/bin/node /usr/local/bin/node
WORKDIR /app/backend
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ ./
COPY --from=web /web/.next/standalone /app/frontend/
COPY --from=web /web/.next/static /app/frontend/.next/static/
COPY infra/liara/nginx.conf /etc/nginx/nginx.conf
COPY infra/liara/start.py /app/start.py
RUN useradd --uid 10001 --create-home app && chmod -R a+rX /app && chmod 644 /etc/nginx/nginx.conf && mkdir -p /tmp/nginx-client /tmp/nginx-proxy && chown -R app:app /tmp/nginx-client /tmp/nginx-proxy
USER app
EXPOSE 8080
CMD ["python", "/app/start.py"]
