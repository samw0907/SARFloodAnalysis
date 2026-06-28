FROM python:3.11-slim

ARG CASE_STUDY

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libexpat1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ${CASE_STUDY}/src/ ./src/
COPY ${CASE_STUDY}/scripts/ ./scripts/
COPY ${CASE_STUDY}/config/ ./config/
COPY ${CASE_STUDY}/pyproject.toml .
RUN pip install --no-cache-dir -e . --no-deps

CMD ["bash", "-c", "python scripts/run_analysis.py && python scripts/make_figures.py"]
