"""Azure credentials shared by the controller function and the code
   borrowed from rctab."""
from azure.identity import DefaultAzureCredential

# We should only need one set of credentials.
CREDENTIALS = DefaultAzureCredential()
