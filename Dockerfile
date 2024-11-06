# Use a base image with Python
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Copy the Flask app files into the container
COPY . /app

# Copy the requirements and install them
# COPY requirements.txt .
RUN pip install -r requirements.txt

# Expose port 8000 for Gunicorn
EXPOSE 5000

# Start Gunicorn server
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "wsgi:app"]
