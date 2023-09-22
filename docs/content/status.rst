Status Function
---------------

`status` is an Azure function for deployment to an Azure Function App.
It will get all the status data for subscriptions that are visible to its Service Principal and send it to an instance of the RCTab web server API.

The `status` function needs to query the Active Directory Graph to resolve the names and email addresses of the service principals (users, groups and manged identities) in a subscription's Role-Based Access Control (RBAC) list.
This returns all principals that have the subscription within their scope and so will retrieve principals with access to a given subscription (e.g. "scope": "/subscriptions/00000000-0000-0000-0000-000000000000") and principals with access to a specific resource or resource group within a subscription (e.g. "scope": "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/Example-Storage-rg/providers/Microsoft.Storage/storageAccounts/azurestorage12345/blobServices/default/containers/blob-container-01").
Several aspects of RCTab rely on this, particularly the email alerts.
This should work out-of-the-box if the function app is running with your identity (e.g. if you run it locally) but it does not work if you use a system-assigned managed identity.
Instead, for Azure deployment, we'll need a service principal.

Running Locally
~~~~~~~~~~~~~~~

The generic instructions in :doc:`setup` should work.

Running On Azure
~~~~~~~~~~~~~~~~

Creating a Service Principal with Graph permissions
+++++++++++++++++++++++++++++++++++++++++++++++++++

The following is taken from `this <https://github.com/Azure/azure-cli/issues/20792#issuecomment-1014183586>`_ GitHub issue.

.. code-block:: shell

   # Create a new service principal
   $ az ad sp create-for-rbac --role Reader --scope /subscriptions/00000000-0000-0000-0000-000000000001
   {
     "appId": "00000000-0000-0000-0000-000000000002",  # This is the Client ID
     "displayName": "azure-2001-01-01-07-00-00",
     "password": "xxx",  # This is the Client Secret
     "tenant": "00000000-0000-0000-0000-000000000003"  # This is the Tenant ID
   }

   # Query its objectId
   $ az ad sp show --id 00000000-0000-0000-0000-000000000002 --query objectId --output tsv
   00000000-0000-0000-0000-000000000004

   # Get the API ID of AD Graph Directory.Read.All and objectId of AD Graph
   $ az ad sp show --id 00000002-0000-0000-c000-000000000000
   {
     "appDisplayName": "Windows Azure Active Directory",
     "appId": "00000002-0000-0000-c000-000000000000",
       {
         "allowedMemberTypes": [
           "Application"
         ],
         "description": "Allows the app to read data in your company or school directory, such as users, groups, and apps.",
         "displayName": "Read directory data",
         "id": "00000000-0000-0000-0000-000000000005",
         "isEnabled": true,
         "value": "Directory.Read.All"
       },
       ...
     "objectId": "00000000-0000-0000-0000-000000000006",
     ...

   # Add permission to the service principal
   $ az ad app permission add --api 00000002-0000-0000-c000-000000000000 --api-permissions 00000000-0000-0000-0000-000000000005=Role --id 00000000-0000-0000-0000-000000000002

   # Grant admin consent
   # DO NOT use the old `az ad app permission admin-consent` API
   $ az rest --method POST --uri https://graph.microsoft.com/v1.0/servicePrincipals/00000000-0000-0000-0000-000000000006/appRoleAssignedTo --body '{"principalId": "00000000-0000-0000-0000-000000000004", "resourceId": "00000000-0000-0000-0000-000000000006", "appRoleId": "00000000-0000-0000-0000-000000000005"}'

Now that we have a service principal with the right graph permissions, we can

#. Create a role on Azure with the `Microsoft.Authorization/roleAssignments/read` permission.
#. Assign the service principal to the role from above over the management group of interest.
#. [untested] Remove the Reader role assignment granted when the service principal was first created.
#. We need to give the app some credentials so that it can authenticate as our new service principal. Take the `appId`, `tenant` and `password` values shown when the service principal was created, above, and set them as client ID, tenant ID and client secretPulumi config values, as described in the RCTab Infrastructure docs.
