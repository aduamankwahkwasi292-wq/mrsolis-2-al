FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render/Railway/most PaaS platforms inject PORT at runtime; server.py reads it.
ENV PORT=8420
EXPOSE 8420

CMD ["python", "-m", "qgen.server"]
