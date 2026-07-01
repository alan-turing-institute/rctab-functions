FROM mcr.microsoft.com/azure-functions/python:4-python3.12-appservice

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

RUN mkdir -p /home/site/wwwroot/usage
COPY usage/*.py /home/site/wwwroot/usage/
COPY usage/function.json /home/site/wwwroot/usage/

RUN mkdir -p /home/site/wwwroot/utils
COPY utils/*.py /home/site/wwwroot/utils/

RUN mkdir -p /home/site/wwwroot/monthly_usage
COPY monthly_usage/*.py /home/site/wwwroot/monthly_usage/
COPY monthly_usage/function.json /home/site/wwwroot/monthly_usage/

WORKDIR /home/site/wwwroot

# Create with poetry export -f requirements.txt --output requirements.txt --only main
COPY requirements.txt ./
RUN apt install git
RUN python -m pip install --target .python_packages/lib/site-packages --requirement requirements.txt --no-deps
