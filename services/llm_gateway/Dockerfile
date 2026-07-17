FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml ./
COPY llm_gateway ./llm_gateway
RUN pip install --no-cache-dir .

EXPOSE 8010
CMD ["python", "-m", "uvicorn", "llm_gateway.main:app", "--host", "0.0.0.0", "--port", "8010"]
