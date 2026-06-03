FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements-api.txt .

RUN pip install --no-cache-dir -r requirements-api.txt

COPY app ./app
COPY data/store_layout.json ./data/store_layout.json

# Copy POS data for conversion rate calculation
COPY data/files/ ./data/files/

# Ensure data directory exists for SQLite DB
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
