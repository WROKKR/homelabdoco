FROM python:3.13-slim
WORKDIR /app
COPY watcher.py death_templates.json ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "watcher.py"]
