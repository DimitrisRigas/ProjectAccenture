from dotenv import load_dotenv
import os

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

load_dotenv()

endpoint = os.getenv("AI_SEARCH_ENDPOINT")
api_key = os.getenv("AI_SEARCH_API_KEY")
index_name = os.getenv("AI_SEARCH_INDEX_NAME")

client = SearchClient(
    endpoint=endpoint,
    index_name=index_name,
    credential=AzureKeyCredential(api_key),
)

print("Testing Azure AI Search index")
print("=" * 80)
print(f"Index name: {index_name}")
print("=" * 80)

results = client.search(
    search_text="*",
    select=["chunk_id", "chunk_text"],
    top=5,
)

count = 0

for result in results:
    count += 1
    print(f"Document {count}")
    print(f"chunk_id: {result.get('chunk_id')}")
    print("chunk_text preview:")
    print((result.get("chunk_text") or "")[:500])
    print("-" * 80)

if count == 0:
    print("No documents found in the index.")
else:
    print(f"Displayed {count} documents.")