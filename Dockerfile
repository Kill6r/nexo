FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md alembic.ini ./
COPY nexo ./nexo
COPY migraciones ./migraciones
COPY herramientas ./herramientas
RUN pip install --no-deps . && useradd --create-home --uid 10001 nexo
USER nexo
EXPOSE 8000
CMD ["uvicorn", "nexo.api.principal:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
