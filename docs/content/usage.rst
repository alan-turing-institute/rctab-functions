Usage Function
--------------

`usage` is an Azure function for deployment to an Azure Function App.
It will get all the usage data in a management group or billing account and send it to an instance of the RCTab web server API.

..
    `costmanagement` is also an Azure function. It can be deployed to the same function app as the `usage` function.

    `monthly_usage` uses similar code as `usage` but runs on the 7th day of each month to get the previous month's usage.

Running Locally
+++++++++++++++

Setup
~~~~~

The generic instructions in :doc:`setup` should work.

Run
~~~

The generic instructions in :doc:`setup` should work.

#. Depending on whether you want to collect usage data for the whole billing account or for a management group, you need to provide either:

   #. the name of a management group as the `MGMT_GROUP` environment variable, or
   #. the ID of your billing account as the `BILLING_ACCOUNT_ID` environment variable.       Note that specifying the billing account ID only work when running the app locally and not on Azure.
   #. Instead of `python run_now.py`, use `python run_usage.py`.

..
   1. This function app has 3 functions so, instead of `python run_now.py`, you will need to run the `usage` and `costmanagement` functions with `python run_usage.py` and `python run_costmanagement.py`, respectively.

Running on Azure
++++++++++++++++

Setup
~~~~~

If you deploy to Azure with the RCTab Infrastructure repository, the function app should start to run immedately.
However, it will only be able to collect data if it has enough permissions:

#. To work, the function app needs at least the `Billing Reader` role over the management group of interest.

There are some settings, which may not be covered by the Infrastructure's Pulumi config, that you may want to edit on occasion:

#. `USAGE_HISTORY_DAYS` is the number of days' usage data to collect and `USAGE_HISTORY_DAYS_OFFSET` is the offset backwards in time.
   `USAGE_HISTORY_DAYS=3` and `USAGE_HISTORY_DAYS_OFFSET=0` are the defaults and will give the last 3 days' usage data.
   `USAGE_HISTORY_DAYS=3` and `USAGE_HISTORY_DAYS_OFFSET=4` would give the 3 days of data ending 4 days ago (so it would collect data for today-7, today-6 and today-5).

Run
~~~

The generic instructions in :doc:`setup` should work.
