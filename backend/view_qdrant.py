import os
import pprint
from qdrant_client import QdrantClient

def view_collection_data():
    """Connects to the local Qdrant DB using the official client and prints the structured payload."""
    # Dynamically find the qdrant_db folder located in the parent directory of backend/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    qdrant_path = os.path.join(base_dir, "qdrant_db")
    
    if not os.path.exists(qdrant_path):
        print(f"Error: Qdrant DB folder not found at '{qdrant_path}'")
        return

    try:
        # 1. Connect using the official QdrantClient
        client = QdrantClient(path=qdrant_path)
        collection_name = "uploaded_docs"
        
        if not client.collection_exists(collection_name):
            print(f"Collection '{collection_name}' does not exist yet.")
            return

        # 2. Scroll through the collection to get the records (fetches up to 100 chunks)
        records, next_page_offset = client.scroll(
            collection_name=collection_name,
            limit=100,
            with_payload=True,
            with_vectors=False # Exclude giant binary vectors to keep the output clean
        )
        
        if not records:
            print(f"No documents found in the '{collection_name}' collection.")
            return
            
        print(f"--- Found {len(records)} documents in the '{collection_name}' collection ---\n")
        
        # 3. Print the cleanly structured metadata and preview content
        for record in records:
            payload = record.payload or {}
            metadata = payload.get("metadata") or {}
            page_content = payload.get("page_content") or ""
            
            print(f"📄 Document Chunk ID: {record.id}")
            print(f"   ├─ File: {metadata.get('filename', 'N/A')}")
            print(f"   ├─ Page: {metadata.get('page', 0) + 1}")
            print(f"   ├─ Type: {metadata.get('document_type', 'N/A')}")
            print(f"   ├─ Segment: {metadata.get('chunk_id', 'N/A')}/{metadata.get('total_chunks', 'N/A')}")
            print(f"   ├─ Owner: {metadata.get('owner', 'N/A')}")
            print("   └─ Content:")
            for line in page_content.splitlines():
                if line.strip():
                    print(f"      {line}")
            print("-" * 50)
            print("\n")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    view_collection_data()
