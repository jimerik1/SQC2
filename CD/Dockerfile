FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set Python path to recognize the src directory
ENV PYTHONPATH=/app
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Set default configuration to production
ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=production

# Expose the port the app will run on
EXPOSE 5000

# Command to run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]