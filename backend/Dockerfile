# Multi-stage build: one image that serves BOTH the API and the built React app.
# Build from the repo root:  docker build -f backend/Dockerfile -t paperai .

# ---- 1) build the frontend ----
FROM node:20-alpine AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2) python runtime ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY shared ./shared
COPY backend ./backend
COPY --from=frontend /fe/dist ./frontend/dist

RUN useradd --create-home appuser && mkdir -p /srv/backend/data && chown -R appuser /srv
USER appuser

WORKDIR /srv/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
