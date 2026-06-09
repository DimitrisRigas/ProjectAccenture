"""
src/delete_azure_search_index.py

Delete one Azure AI Search index.
Run locally.
"""

from dotenv import load_dotenv
import os

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient


load_dotenv()

AI_SEARCH_ENDPOINT = os.getenv("AI_SEARCH_ENDPOINT")
AI_SEARCH_API_KEY = os.getenv("AI_SEARCH_API_KEY")

INDEX_TO_DELETE = "team4"

client = SearchIndexClient(
    endpoint=AI_SEARCH_ENDPOINT,
    credential=AzureKeyCredential(AI_SEARCH_API_KEY),
)

print(f"Deleting index: {INDEX_TO_DELETE}")

client.delete_index(INDEX_TO_DELETE)

print("Deleted.")