FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ backend/
COPY evaluation/ evaluation/
COPY gunicorn.conf.py ./
COPY --from=frontend-build /build/frontend/dist frontend/dist
RUN useradd --system --uid 10001 app
USER app
EXPOSE 10000
CMD ["python", "-m", "backend.start"]
