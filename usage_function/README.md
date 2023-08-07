# Usage

`usage` is an Azure function for deployment to an Azure Function App.
It will get all the usage data for subscriptions in a management group or billing account and send it to an instance of [RCTab](https://github.com/alan-turing-institute/rctab-api).

`costmanagement` is also an Azure function. It should be deployed to the same function app as the `usage` function.

`monthly_usage` uses similar code as `usage` but runs on the 7th day of each month to get the previous month's usage.

## Running Locally

### Setup

The generic instructions in the repo [README](../README.md) should work.

### Run

The generic instructions in the repo [README](../README.md) should work except that:

1. Depending on whether you want to collect usage data for the whole billing account or for a management group, you need to provide either:
   1. the name of a management group as the `MGMT_GROUP` environment variable, or
   1. the ID of your billing account as the `BILLING_ACCOUNT_ID` environment variable
1. This function app has 3 functions so, instead of `python run_now.py`, you will need to run the `usage` and `costmanagement` functions with `python run_usage.py` and `python run_costmanagement.py`, respectively.

## Running on Azure

### Setup

The generic instructions in the repo [README](../README.md) should work except that:

1. To work, the function app needs at least the `Billing Reader` role over the management group or billing account of interest.
1. `USAGE_HISTORY_DAYS` is the number of days' usage data to collect and `USAGE_HISTORY_DAYS_OFFSET` is the offset backwards in time.
  `USAGE_HISTORY_DAYS=3` and `USAGE_HISTORY_DAYS_OFFSET=0` are the defaults and will give the last 3 days' usage data.
  `USAGE_HISTORY_DAYS=3` and `USAGE_HISTORY_DAYS_OFFSET=3` would give the 3 days of data ending 3 days ago.
1. Depending on whether you want to collect usage data for the whole billing account or for a management group, you need to provide either:
   1. the name of a management group as the `MGMT_GROUP` environment variable, or
   1. the ID of your billing account as the `BILLING_ACCOUNT_ID` environment variable

ToDo: clarify what permissions are needed for the Billing Account option.

### Run

The generic instructions in the repo [README](../README.md) should work.
