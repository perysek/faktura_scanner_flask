# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Flask settings
    FLASK_APP=app.py \
    FLASK_DEBUG=0 \
    # Tesseract and Poppler paths (Linux locations)
    TESSERACT_CMD=/usr/bin/tesseract \
    POPPLER_PATH=/usr/bin

# Install system dependencies
# - tesseract-ocr & tesseract-ocr-pol: for OCR (Polish language)
# - poppler-utils: for PDF processing
# - libgl1-mesa-glx & libglib2.0-0: for OpenCV
# - nodejs & npm: for building TailwindCSS
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-pol \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    nodejs \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Install Node.js dependencies (Tailwind)
COPY package.json .
# COPY package-lock.json .  # Uncomment if you have a package-lock.json
RUN npm install

# Copy project code
COPY . .

# Build TailwindCSS
RUN npm run build:css

# Create necessary directories
RUN mkdir -p uploads pdfs assets/temp

# Expose port
EXPOSE 8083

# Run the application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8083", "app:create_app()"]
