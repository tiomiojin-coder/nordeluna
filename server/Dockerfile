FROM python:3.12-slim
WORKDIR /srv/nordeluna
COPY relay.py start.py ./
ENV PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8765 DB_PATH=/data/relay.sqlite3
EXPOSE 8765
CMD ["python", "start.py"]
