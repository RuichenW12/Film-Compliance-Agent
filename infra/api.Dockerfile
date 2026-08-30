FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# `.[cloud]` -- not `.[api]`, which was never a declared extra. pip treats an
# unknown extra as a warning rather than an error, so the old line installed the
# base package and moved on; nothing failed until something needed Firestore.
# `cloud` pulls in the Firestore, Storage, Pub/Sub and Gemini clients.
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[cloud]"

COPY . .

# Cloud Run supplies PORT and may not use 8080. Honouring it is required: a
# container listening on a fixed port is marked unhealthy and the revision
# never receives traffic.
ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
