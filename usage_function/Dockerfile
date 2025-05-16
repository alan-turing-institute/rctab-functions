FROM mcr.microsoft.com/azure-functions/python:4-python3.10-appservice

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

RUN curl -sSL https://install.python-poetry.org | python3 -

RUN mkdir -p /home/site/wwwroot/usage
COPY usage/*.py /home/site/wwwroot/usage/
COPY usage/function.json /home/site/wwwroot/usage/

RUN mkdir -p /home/site/wwwroot/utils
COPY utils/*.py /home/site/wwwroot/utils/

RUN mkdir -p /home/site/wwwroot/monthly_usage
COPY monthly_usage/*.py /home/site/wwwroot/monthly_usage/
COPY monthly_usage/function.json /home/site/wwwroot/monthly_usage/

WORKDIR /home/site/wwwroot

RUN ~/.local/share/pypoetry/venv/bin/poetry config virtualenvs.create false

COPY host.json pyproject.toml poetry.lock ./

RUN ~/.local/share/pypoetry/venv/bin/poetry install --only main
