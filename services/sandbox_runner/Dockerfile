FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml ./
COPY sandbox_runner ./sandbox_runner
COPY sandbox_image ./sandbox_image
RUN pip install --no-cache-dir .

EXPOSE 8020
CMD ["python", "-m", "uvicorn", "sandbox_runner.main:app", "--host", "0.0.0.0", "--port", "8020"]
