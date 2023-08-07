FROM mcr.microsoft.com/azure-functions/python:4-python3.10

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

RUN curl -sSL https://install.python-poetry.org | python3 -
RUN ~/.local/share/pypoetry/venv/bin/poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./

RUN ~/.local/share/pypoetry/venv/bin/poetry install --only main

RUN mkdir -p /home/site/wwwroot/status
COPY status/*.py /home/site/wwwroot/status/
COPY status/function.json /home/site/wwwroot/status/
