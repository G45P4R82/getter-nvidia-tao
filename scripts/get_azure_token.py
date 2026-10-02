#!/usr/bin/env python3
"""Print an Azure AI bearer token for CI use."""

import os

from azure.identity import ClientSecretCredential


credential = ClientSecretCredential(
    tenant_id=os.environ["AZURE_TENANT_ID"],
    client_id=os.environ["AZURE_CLIENT_ID"],
    client_secret=os.environ["AZURE_CLIENT_SECRET"],
)
print(credential.get_token("https://ai.azure.com/.default").token)
