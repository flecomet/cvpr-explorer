FROM python:3.11-slim

EXPOSE 8050

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install -r requirements.txt

COPY app.py .
COPY data/ data/

CMD ["python", "app.py"]
