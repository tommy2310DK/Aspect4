FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for zeep/xml handling)
# getting libxml2-dev etc might be needed for lxml which zeep uses, 
# but usually binary wheels cover it.

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
