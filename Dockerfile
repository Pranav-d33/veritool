FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

# Install OPA 1.2.0 (for benchmark comparison)
RUN curl -sL -o /usr/local/bin/opa \
    https://github.com/open-policy-agent/opa/releases/download/v1.2.0/opa_linux_amd64_static && \
    chmod +x /usr/local/bin/opa

# Install Lean 4.15.0
RUN curl -sL \
    https://github.com/leanprover/lean4/releases/download/v4.15.0/lean-4.15.0-linux-x86_64.tar.gz \
    | tar xz -C /usr/local --strip-components=1

# Install VeriTool
WORKDIR /app
COPY . .
RUN pip install -e .

CMD ["make", "all"]
