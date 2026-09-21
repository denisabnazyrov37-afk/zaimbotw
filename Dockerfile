FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY .env.example .env.example

RUN mkdir -p /app/data/uploads /app/data/contracts

CMD ["python", "-m", "app"]
