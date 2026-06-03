FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["bash", "-c", "fastapi-m8-prestart && uvicorn fastapi_minimal.main:app --host 0.0.0.0 --port 8000"]
