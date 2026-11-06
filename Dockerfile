FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PORT=8501
WORKDIR /app
COPY study_assistant/requirements.lock.txt /app/requirements.txt
RUN pip install -r requirements.txt
COPY study_assistant /app/study_assistant
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8501')+'/_stcore/health')"
ENTRYPOINT ["/app/start.sh"]
