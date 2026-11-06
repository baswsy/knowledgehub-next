#!/bin/sh
set -eu
# Persist every mutable directory on the same attached disk.
mkdir -p /app/persistent
for name in data materials runs exports; do
    mkdir -p "/app/persistent/$name"
    if [ -d "/app/study_assistant/$name" ] && [ ! -L "/app/study_assistant/$name" ]; then
        cp -an "/app/study_assistant/$name/." "/app/persistent/$name/"
        rm -rf "/app/study_assistant/$name"
    fi
    if [ ! -L "/app/study_assistant/$name" ]; then
        ln -s "/app/persistent/$name" "/app/study_assistant/$name"
    fi
done
if [ "${APP_MODE:-streamlit}" = "api" ]; then
    exec uvicorn web_api:app --app-dir /app/study_assistant --host 0.0.0.0 --port "${PORT:-8000}"
fi
exec streamlit run /app/study_assistant/app.py --server.address=0.0.0.0 --server.port="${PORT:-8501}" --browser.gatherUsageStats=false
