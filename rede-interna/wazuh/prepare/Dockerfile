FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir bcrypt==4.3.0
COPY prepare.py /prepare.py
ENTRYPOINT ["python", "/prepare.py"]
