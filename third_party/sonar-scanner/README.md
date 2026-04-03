# Sonar Scanner (vendored tool)

Sonar Scanner is stored directly in this repository at a fixed version:
- `7.0.2.4839`

Docker build does **not** download Sonar Scanner from the network. It expects
the scanner binary to exist under one of these paths:

- `sonar-scanner-7.0.2.4839-linux-x64/bin/sonar-scanner`
- `sonar-scanner-7.0.2.4839-linux-aarch64/bin/sonar-scanner`
