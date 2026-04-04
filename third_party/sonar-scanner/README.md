# Sonar Scanner

Sonar Scanner is downloaded automatically from the official SonarSource CDN
during `docker build`. No manual setup is required.

**Version:** `7.0.2.4839`
**CDN base:** `https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/`

The correct architecture variant (`linux-x64` or `linux-aarch64`) is selected
at build time via `dpkg --print-architecture`. The `ARG SONAR_SCANNER_VERSION`
in the `Dockerfile` controls the pinned version.

Local extracted directories (`sonar-scanner-*-linux-*/`) are excluded from
version control via `.gitignore`.
