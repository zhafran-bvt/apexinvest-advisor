# Dockerfile for the ApexInvest Advisor backend service
#
# This container installs the necessary Python dependencies, copies the
# application code along with the trained model and dataset and then
# launches the FastAPI server via Uvicorn.  The image is based on
# python:3.10-slim to keep the footprint small.  All components used
# here are free and open source.

FROM python:3.10-slim

# Create a non‑root user for security (optional)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source and assets.  We assume that the build
# context is the project root and that the model and dataset have been
# generated ahead of time.  Adjust these paths as necessary when
# building locally or in your CI pipeline.
# Copy the entire repo into /app so the backend, ETL, and model code are present.
# We avoid copying from parent paths (..) to be compatible with remote builders.
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
