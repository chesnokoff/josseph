FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip git openjdk-21-jre-headless nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir --retries 10 --timeout 120 -r /tmp/requirements.txt

ENV SONAR_SCANNER_VERSION=7.0.2.4839
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) scanner_zip_pkg="sonar-scanner-cli-${SONAR_SCANNER_VERSION}-linux-x64"; scanner_dir_pkg="sonar-scanner-${SONAR_SCANNER_VERSION}-linux-x64" ;; \
      arm64) scanner_zip_pkg="sonar-scanner-cli-${SONAR_SCANNER_VERSION}-linux-aarch64"; scanner_dir_pkg="sonar-scanner-${SONAR_SCANNER_VERSION}-linux-aarch64" ;; \
      *) echo "Unsupported architecture: $arch"; exit 1 ;; \
    esac; \
    scanner_url="https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/${scanner_zip_pkg}.zip"; \
    curl -fL --retry 10 --retry-all-errors --retry-delay 2 --connect-timeout 20 --max-time 600 "$scanner_url" -o /tmp/sonar-scanner.zip; \
    unzip -q /tmp/sonar-scanner.zip -d /opt; \
    ln -s "/opt/${scanner_dir_pkg}/bin/sonar-scanner" /usr/local/bin/sonar-scanner; \
    rm -f /tmp/sonar-scanner.zip

COPY . /app

CMD ["python", "-m", "josseph"]
