# RCTab Management Functions

[![Documentation Status](https://readthedocs.org/projects/rctab-functions/badge/?version=latest)](https://rctab-functions.readthedocs.io/en/latest/?badge=latest)

The RCTab Management Functions and scripts for deploying as Azure Function Apps.

## Contents

- [Function Apps](#function-apps)
- [Additional Components](#additional-components)
- [Development Setup](#development-setup)
- [Infrastructure Deployment](#infrastructure-deployment)

## Function Apps

There are three function apps:

1. [billing_function](./billing_function/) collects data on how much each subscription has spent
1. [status_function](./status_function/) collects data on how much each subscription has spent
1. [controller_function](./controller_function/) turns subscriptions on/off according to their expiry data and remaining budget

## Additional Components

The [RCTab.md](https://github.com/alan-turing-institute/rctab-api/blob/master/RCTab.md) document gives an overview of the whole system, of which the function apps are only one part.

## Running Locally

Even though the three function apps are designed to run on Azure, it is easy to run them locally for development.
The general process to install dependencies and run the function apps is outlined below but you should also check each function app's README in case there are more specific requirements.

### Pre-requisites

1. [Install poetry](https://python-poetry.org/docs/#osx--linux--bashonwindows-install-instructions).
  This is used to manage virtual environments and package dependencies.
1. Install pyenv (e.g. with `brew install pyenv`).
  This is optional but useful for matching Python versions between development and production.See [here](https://blog.jayway.com/2019/12/28/pyenv-poetry-saviours-in-the-python-chaos/) for more detailed instructions.
1. Install pre-commit (e.g. with `brew install pre-commit`).
  This is used to run linters and other static checks during Git commits.

### Setup

1. `cd` into the function app's directory.
1. Install the requirements with
   - `pyenv local 3.10.x` to set the local Python version with pyenv to match that in `pyproject.toml`.
   - `poetry env use $(which python)` to tell Poetry the Python version to use.
   - `poetry install` to install dependencies into a new Poetry environment.
   - `poetry shell` to activate the new environment.
1. Set the host or IP of the listening web server, which will probably be a local one.
  For example, `export API_URL=http://127.0.0.1:8000`. Note, avoid using `http://localhost:8000` as Pydantic will produce a URL validation error about missing top level domain.
1. Set an environment variable called `RCTAB_TENANT_ID`, which should contain your organisation's Azure Active Directory tenant ID.
1. Generate a public/private key pair with `ssh-keygen -t rsa`.
  Set an environment variable called `PRIVATE_KEY` with the contents of the private key file, for example, `export PRIVATE_KEY=$(cat /path/to/private/key/file)`.
  You will need to provide the public part of the key pair to the [RCTab-API](https://github.com/alan-turing-institute/rctab-api).

**Note** Instead of setting the environment variables in the terminal, you can put them in a `.env` file.

### Run

1. Make sure that the right Poetry environment is activated.
1. Run the function with `python run_now.py`.

## Deployment to Azure

### Setup

1. Set up a Function App on Azure, either:
   - with Pulumi, by following [INFRASTRUCTURE.md](INFRASTRUCTURE.md).
   - manually (e.g. with the Azure CLI or via [portal.azure.com](portal.azure.com)), in which case you should still refer to the Pulumi `.py` files so that you choose the right OS, function version, language runtime, app service plan, etc.
1. You can now deploy the functions to the function app either:
   1. manually:
      - Use poetry to generate an up-to-date requirements.txt file, removing `pywin32` as it isn't needed, with `poetry export --without-hashes | sed '/pywin/d' > requirements.txt`.
      - Install the Azure `func` CLI as described [here](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=v4%2Cmacos%2Ccsharp%2Cportal%2Cbash#install-the-azure-functions-core-tools).
      - Deploy to Azure with `func azure functionapp publish function-app-name`, replacing `function-app-name` with the name of your Azure function app.
   1. with a GitHub Action:
      - Get your Function App's publish profile
      - Set it as a repository secret so that your function is deployed by our GitHub Action whenever there are changes to the `main` branch.
      - See our Action [file](.github/workflows/staging_deployment_billing.yml) and the Azure Function Action [docs](https://github.com/marketplace/actions/azure-functions-action#using-publish-profile-as-deployment-credential-recommended) for more.
1. Set the same environment variables as for local development, except that the server URL will be the Azure one. For example, `export API_URL=http://myapp.azurewebsites.com:80`.

### Run

1. The function app will run according to the cron expression in its `function.json`.
1. You can force the function to run by following [these](https://docs.microsoft.com/en-us/azure/azure-functions/functions-manually-run-non-http) instructions.
  Or, if you are using [httpie](https://httpie.io/), by running:

   ```bash
   http POST https://your-function-app.azurewebsites.net/admin/functions/function-name '{APP_KEY}' 'Content-Type:application/json' input=test
   ```

   where APP_KEY is the `_master` key at [portal.azure.com](portal.azure.com) -> your-function-app -> "App keys" -> "Host keys".
