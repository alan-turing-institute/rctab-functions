FROM mcr.microsoft.com/azure-functions/python:4-python3.12-appservice

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

COPY controller /home/site/wwwroot/controller

WORKDIR /home/site/wwwroot/

# Create with poetry export -f requirements.txt --output requirements.txt --only main
COPY requirements.txt ./
RUN python -m pip install --target .python_packages/lib/site-packages --requirement requirements.txt --no-deps
