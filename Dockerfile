FROM python:3.11-slim-bookworm

WORKDIR /app

RUN python -V

# Install build tools, ffmpeg and portaudio
RUN apt-get update && apt-get install -y build-essential ffmpeg portaudio19-dev git

# Install pip
RUN pip install --upgrade pip

# Install dependencies
COPY requirements.txt ./
RUN pip install -U -r requirements.txt

# Set Python path
ENV PYTHONPATH=/app
