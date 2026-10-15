FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY openfresh ./openfresh

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "openfresh.app_factory:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
