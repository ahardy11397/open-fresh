FROM node:22-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml ./
COPY backend/openfresh ./openfresh
RUN pip install --no-cache-dir .
COPY --from=frontend-build /frontend/dist /app/static
EXPOSE 4269
CMD ["uvicorn", "openfresh.app_factory:create_app", "--factory", "--host", "0.0.0.0", "--port", "4269"]
