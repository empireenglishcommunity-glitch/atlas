FROM python:3.12-slim

# tzdata so Africa/Cairo resolves inside the container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Africa/Cairo

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# runtime data (SQLite + markdown archive + audio cache) lives on a mounted volume
RUN mkdir -p /app/data

CMD ["python", "-m", "src.atlas.bot"]
