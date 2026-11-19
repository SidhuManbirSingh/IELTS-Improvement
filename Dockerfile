FROM python:3.12-slim

WORKDIR /app

COPY server.py index.html ./

EXPOSE 8501

ENV PORT=8501

CMD ["python", "-u", "server.py"]
