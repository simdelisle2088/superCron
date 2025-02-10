FROM python:3.12.3-alpine3.19

WORKDIR /server

RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    mariadb-dev \
    python3-dev \
    build-base

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY server .

COPY .env.development .env

# Expose the port the app runs on
EXPOSE 8016

# Set environment variables
ENV PYTHONPATH=/server
ENV HOST=0.0.0.0
ENV PORT=8016
ENV LOG_LEVEL=info
ENV WORKERS=2
ENV APP_ENV=development

# Use the correct module path in the command
CMD ["sh", "-c", "uvicorn main:app --host $HOST --port $PORT --log-level $LOG_LEVEL --workers $WORKERS"]

