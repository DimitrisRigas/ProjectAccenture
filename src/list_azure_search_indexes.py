"""
src/list_azure_search_indexes.py

List all Azure AI Search indexes.
Run locally.
"""

from dotenv import load_dotenv
import os

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient


load_dotenv()

AI_SEARCH_ENDPOINT = os.getenv("AI_SEARCH_ENDPOINT")
AI_SEARCH_API_KEY = os.getenv("AI_SEARCH_API_KEY")

client = SearchIndexClient(
    endpoint=AI_SEARCH_ENDPOINT,
    credential=AzureKeyCredential(AI_SEARCH_API_KEY),
)

print("=" * 100)
print("Azure AI Search indexes")
print("=" * 100)

indexes = list(client.list_indexes())

for index in indexes:
    print(index.name)

print("=" * 100)
print(f"Total indexes: {len(indexes)}")
print("=" * 100)