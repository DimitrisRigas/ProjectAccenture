from dotenv import load_dotenv
import os

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient

load_dotenv()

endpoint = os.getenv("AI_SEARCH_ENDPOINT")
api_key = os.getenv("AI_SEARCH_API_KEY")
index_name = os.getenv("AI_SEARCH_INDEX_NAME")

client = SearchIndexClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(api_key),
)

index = client.get_index(index_name)

print("Fields in index:")
print("=" * 80)

for field in index.fields:
    print(field.name)