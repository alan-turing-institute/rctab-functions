Controller Function
-------------------

`controller` is an Azure function for deployment to an Azure Function App.
It will poll the RCTab web server API for a list of subscriptions that ought to be disabled or enabled.

Local Setup
~~~~~~~~~~~

The generic instructions in :doc:`setup` should work.

Azure Setup
~~~~~~~~~~~

The generic instructions in :doc:`setup` should work but note that:

#. This function requires a role with a certain level of permission across subscriptions.
   Therefore, this function's managed identity should be given a role (either the `owner` role or a new role) that possess `Microsoft.Authorization/*` and `Microsoft.Subscription/*` permissions over an Azure Management Group.
