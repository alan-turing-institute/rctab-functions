# Installation

## Running Locally

The function apps are typically deployed automatically via Pulumi (see the RCTab Infrastructure docs). However, it is easy to run them locally for development.
The general process to install dependencies and run the function apps is outlined below but you should also check each function app's page in case there are more specific requirements.

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
1. Set the host or IP of the listening RCTab web server, which will probably be a local one.
  For example, `export API_URL=http://127.0.0.1:8000`.
  Note, avoid using `http://localhost:8000` as Pydantic will produce a URL validation error about missing top level domain.
1. Set an environment variable called `RCTAB_TENANT_ID`, which should contain your organisation's Azure Active Directory tenant ID.
1. Generate a public/private key pair with `ssh-keygen -t rsa`.
  Set an environment variable called `PRIVATE_KEY` with the contents of the private key file, for example, `export PRIVATE_KEY=$(cat /path/to/private/key/file)`.
  You will need to provide the public part of the key pair to the [RCTab API](https://rctab-api.readthedocs.io).

**Note** Instead of setting the environment variables in the terminal, you can put them in a `.env` file.

### Run

1. Make sure that the right Poetry environment is activated.
1. Run the function with `python run_now.py`.

## Running on Azure

### Setup

You should create function apps on Azure using by deploying RCTab with the Infrastructure repo.
By default, functions deployed this way will pull the latest RCTab images from DockerHub.
If you want to deploy custom code to your function apps, you will need a container registry, which you can get by signing up to DockerHub or by setting up an Azure Container Registry.
You can either build and push images to your registry manually or by forking the functions repo and using the deployment GitHub workflow.

### Run

1. The function app will run according to the cron expression in its `function.json`.
1. You can force the function to run by following [these](https://docs.microsoft.com/en-us/azure/azure-functions/functions-manually-run-non-http) instructions.
  Or, if you are using [httpie](https://httpie.io/), by running:

   ```bash
   http POST https://your-function-app.azurewebsites.net/admin/functions/function-name '{APP_KEY}' 'Content-Type:application/json' input=test
   ```

   where APP_KEY is the `_master` key at [portal.azure.com](https://portal.azure.com) -> your-function-app -> "App keys" -> "Host keys".
