FROM python:3.11.12-slim

ARG SONAR_SCANNER_VERSION=7.0.2.4839

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openjdk-21-jre-headless nodejs curl unzip \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir --retries 10 --timeout 120 -r /tmp/requirements.txt

# Download Sonar Scanner from official CDN, selecting the correct arch variant
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) arch_tag="linux-x64" ;; \
      arm64) arch_tag="linux-aarch64" ;; \
      *) echo "Unsupported architecture: $arch"; exit 1 ;; \
    esac; \
    pkg="sonar-scanner-cli-${SONAR_SCANNER_VERSION}-${arch_tag}"; \
    url="https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/${pkg}.zip"; \
    curl -fsSL "$url" -o /tmp/sonar-scanner.zip; \
    unzip -q /tmp/sonar-scanner.zip -d /opt; \
    rm /tmp/sonar-scanner.zip; \
    ln -sf "/opt/sonar-scanner-${SONAR_SCANNER_VERSION}-${arch_tag}/bin/sonar-scanner" /usr/local/bin/sonar-scanner

COPY . /app

ENTRYPOINT ["python", "-m", "josseph"]
CMD ["/app/configs/config.yaml"]
