# Controller

`controller` is an Azure function for deployment to an Azure Function App.
It will get a list of subscriptions that ought to be disabled from an instance of [RCTab](https://github.com/alan-turing-institute/rctab-api) and will try to disable them.

## Running Locally

### Setup

The generic instructions in the repo [README](../README.md) should work except that:

1. The private key environment variable is called `PRIVATE_KEY`.

### Run

The generic instructions in the repo [README](../README.md) should work.

### On Azure

#### Setup

The generic instructions in the repo [README](../README.md) should work except that:

1. This function requires a role with a certain level of permission across subscriptions. For this to work, the function needs a managed identity with a role (either the `owner` role or a new role) that possess `Microsoft.Authorization/*` and `Microsoft.Subscription/*` permissions over a defined Management Group with a given name.
1. The private key environment variable is called `PRIVATE_KEY`.

#### Run

The generic instructions in the repo [README](../README.md) should work.
