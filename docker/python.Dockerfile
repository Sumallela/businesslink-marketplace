# One Python image for both the ETL and the Streamlit viewer, so every teammate
# runs the same Python + library versions regardless of what is on their laptop.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The project folder is mounted at /app at run time (see docker-compose.yml),
# so code changes show up without rebuilding the image.
ENV PYTHONUNBUFFERED=1
