FROM python:3.12-slim
WORKDIR /app
COPY config.py server.py bot.py ./
COPY web ./web
COPY tools ./tools
RUN mkdir -p data && pip install --no-cache-dir psycopg2-binary
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["python3", "server.py"]
