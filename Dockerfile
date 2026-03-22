FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openjdk-21-jre-headless nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir --retries 10 --timeout 120 -r /tmp/requirements.txt

COPY . /app

RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) scanner_dir_pkg="sonar-scanner-7.0.2.4839-linux-x64" ;; \
      arm64) scanner_dir_pkg="sonar-scanner-7.0.2.4839-linux-aarch64" ;; \
      *) echo "Unsupported architecture: $arch"; exit 1 ;; \
    esac; \
    scanner_bin="/app/third_party/sonar-scanner/${scanner_dir_pkg}/bin/sonar-scanner"; \
    if [ ! -x "$scanner_bin" ]; then \
      echo "Missing vendored Sonar Scanner: $scanner_bin"; \
      echo "Commit the required sonar-scanner directory under third_party/sonar-scanner."; \
      exit 1; \
    fi; \
    ln -sf "$scanner_bin" /usr/local/bin/sonar-scanner

ENTRYPOINT ["python", "-m", "josseph"]
CMD ["/app/configs/config.yaml"]
