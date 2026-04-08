FROM python:3.11-slim

WORKDIR /app

COPY requirements_nebraska.txt .
RUN pip install --no-cache-dir -r requirements_nebraska.txt

COPY . .

CMD uvicorn nebraska_3_0_api:app --host 0.0.0.0 --port ${PORT:-8000}
