FROM mcr.microsoft.com/azure-functions/python:4-python3.13-appservice

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

RUN mkdir -p /home/site/wwwroot/status
COPY status/*.py /home/site/wwwroot/status/
COPY status/function.json /home/site/wwwroot/status/

WORKDIR /home/site/wwwroot

# Create with poetry export -f requirements.txt --output requirements.txt --only main
COPY requirements.txt ./
RUN apt install -y git
RUN python -m pip install --target .python_packages/lib/site-packages --requirement requirements.txt --no-deps
