FROM python:3.13-slim
WORKDIR /srv/civictrack
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY alembic.ini ./alembic.ini
ENV DEMO_MODE=true
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
