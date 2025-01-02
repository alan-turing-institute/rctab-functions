# Usage

`usage` is an Azure function for deployment to an Azure Function App.
It will get all the usage data for subscriptions in a management group or billing account and send it to an instance of [RCTab](https://github.com/alan-turing-institute/rctab-api).

`costmanagement` is also an Azure function. It should be deployed to the same function app as the `usage` function.

`monthlyusage` uses similar code as `usage` but runs bi-hourly on the 7th and 8th day of each month to get the previous month's usage.

See the docs for more.
