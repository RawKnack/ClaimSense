FROM python:3.12-slim

# Install system dependencies for Tesseract OCR and OpenCV
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app

# Copy requirements first to leverage caching
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy the policy and rules documents needed by config.py
COPY policy_terms.json /app/policy_terms.json
COPY adjudication_rules.md /app/adjudication_rules.md

# Copy the backend code
COPY backend /app/backend

WORKDIR /app/backend

# Expose port
EXPOSE 8000

# Start Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "."]
