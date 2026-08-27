FROM mcr.microsoft.com/azure-functions/python:4-python3.13-appservice

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

WORKDIR /home/site/wwwroot/

# Create with poetry export -f requirements.txt --output requirements.txt --only main --without-hashes
COPY requirements.txt ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && python -m pip install --no-cache-dir --target .python_packages/lib/site-packages --requirement requirements.txt --no-deps \
    && apt-get purge -y --auto-remove git \
    && rm -rf /var/lib/apt/lists/*

COPY host.json ./
COPY controller /home/site/wwwroot/controller
