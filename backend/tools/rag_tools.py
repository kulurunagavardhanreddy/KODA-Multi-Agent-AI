# rag_tools.py

from langchain_core.tools import tool
from qdrant_client.http import models
from backend.loaders.document_loader import get_vector_store, get_shared_qdrant_client
import os

def get_document_search_tool(user_id: str):
    @tool
    def document_search_tool(query: str) -> str:
        """Searches the uploaded documents (PDFs/TXTs) for information matching the user's query.
        Always use this tool first if the user asks about a document they uploaded.
        IMPORTANT: Read the returned document chunks carefully, extract ONLY the exact entities requested  and ignore irrelevant text."""
        try:
            vector_store = get_vector_store()
            
            # 🔒 SECURITY: Apply payload filter to ONLY return chunks owned by the logged-in user
            qdrant_filter = models.Filter(
                must=[models.FieldCondition(key="metadata.owner", match=models.MatchValue(value=user_id))]
            )
            
            # 1. Retrieve initial Top-K similarity matches
            print("\n" + "="*60)
            print(f"🔍 [RAG QUERY]: '{query}'")
            print(f"🔒 [USER ID]: {user_id}")
            print("="*60)
            
            docs = vector_store.similarity_search(query, k=3, filter=qdrant_filter)
            if not docs:
                print("⚠️  [Qdrant DB] No relevant information found in the database.")
                return "No relevant information found in your uploaded documents."
            
            print(f"✅ [Qdrant DB] Successfully retrieved {len(docs)} initial similarity matches:")
            for d in docs:
                print(f"   • File: {d.metadata.get('filename')}, Chunk ID: {d.metadata.get('chunk_id')}, Page: {d.metadata.get('page')}")
            
            # 2. Adaptive Neighbor Target Expansion
            targets = {}  # {filename: set(chunk_ids)}
            for doc in docs:
                filename = doc.metadata.get("filename", doc.metadata.get("source", "unknown"))
                if isinstance(filename, str):
                    filename = os.path.basename(filename)
                
                chunk_id = doc.metadata.get("chunk_id")
                total_chunks = doc.metadata.get("total_chunks")
                
                if chunk_id is not None:
                    # Adaptive window size based on document size
                    if total_chunks is not None and total_chunks <= 10:
                        window = 2  # Short doc/resume: expand +/-2 to capture entire page layout
                    else:
                        window = 1  # Long doc/book: expand +/-1 to optimize prompt size
                        
                    start_idx = max(0, chunk_id - window)
                    end_idx = min(total_chunks if total_chunks is not None else 9999, chunk_id + window + 1)
                    
                    if filename not in targets:
                        targets[filename] = set()
                    targets[filename].update(range(start_idx, end_idx))

            print(f"📋 [RAG Targets for Expansion]: {targets}")

            # 3. Bulk Fetch Neighbor Payloads in single round-trip queries
            all_records = []
            client = get_shared_qdrant_client()
            collection_name = "uploaded_docs"
            
            for filename, chunk_ids in targets.items():
                try:
                    if chunk_ids:
                        must_conditions = [
                            models.FieldCondition(key="metadata.owner", match=models.MatchValue(value=user_id)),
                            models.FieldCondition(key="metadata.filename", match=models.MatchValue(value=filename)),
                            models.FieldCondition(key="metadata.chunk_id", match=models.MatchAny(any=list(chunk_ids)))
                        ]
                        records, _ = client.scroll(
                            collection_name=collection_name,
                            scroll_filter=models.Filter(must=must_conditions),
                            limit=100,
                            with_payload=True,
                            with_vectors=False
                        )
                        all_records.extend(records)
                except Exception as qe:
                    print(f"⚠️  [Qdrant DB] Bulk neighbor lookup failed for {filename}: {qe}")

            print(f"📥 [Qdrant DB] Bulk fetched {len(all_records)} neighbor/expanded chunks.")

            # 4. Merge and Deduplicate Adjacent Chunks
            merged_docs = {}  # {filename: {chunk_id: text}}
            metadata_cache = {}  # {filename: {chunk_id: metadata}}
            
            # Map initial docs
            for doc in docs:
                fname = doc.metadata.get("filename", doc.metadata.get("source", "unknown"))
                if isinstance(fname, str):
                    fname = os.path.basename(fname)
                cid = doc.metadata.get("chunk_id")
                if cid is not None:
                    if fname not in merged_docs:
                        merged_docs[fname] = {}
                        metadata_cache[fname] = {}
                    merged_docs[fname][cid] = doc.page_content
                    metadata_cache[fname][cid] = doc.metadata
                    
            # Map scroll records
            for record in all_records:
                payload = record.payload or {}
                meta = payload.get("metadata") or {}
                fname = meta.get("filename", "unknown")
                cid = meta.get("chunk_id")
                page_content = payload.get("page_content", "")
                if cid is not None:
                    if fname not in merged_docs:
                        merged_docs[fname] = {}
                        metadata_cache[fname] = {}
                    merged_docs[fname][cid] = page_content
                    metadata_cache[fname][cid] = meta

            # 5. Group Contiguous Segments
            results = []
            for fname, chunks_dict in merged_docs.items():
                sorted_ids = sorted(chunks_dict.keys())
                
                # Identify consecutive runs of chunk IDs
                groups = []
                if sorted_ids:
                    current_group = [sorted_ids[0]]
                    for cid in sorted_ids[1:]:
                        if cid == current_group[-1] + 1:
                            current_group.append(cid)
                        else:
                            groups.append(current_group)
                            current_group = [cid]
                    groups.append(current_group)
                
                # Construct combined context for each run
                for group in groups:
                    first_cid = group[0]
                    meta = metadata_cache[fname][first_cid]
                    total_chunks = meta.get("total_chunks", len(chunks_dict))
                    
                    pages = sorted(list(set(metadata_cache[fname][cid].get("page", 0) + 1 for cid in group)))
                    pages_str = ", ".join(map(str, pages))
                    
                    merged_text = "\n".join(chunks_dict[cid] for cid in group)
                    
                    header = f"--- Document Excerpt | Source: {fname} | Page(s): {pages_str} | Segments: {group[0]+1}-{group[-1]+1}/{total_chunks} ---"
                    results.append(f"{header}\n{merged_text}\n")
                    
            print(f"🧩 [Qdrant DB] Reconstructed document text into {len(results)} contiguous context blocks:")
            for idx, res in enumerate(results):
                print(f"  --- Contiguous Block {idx+1} (Preview) ---")
                print("\n".join("      " + line for line in res.split("\n")[:10]) + "\n      ...")
            print("="*60 + "\n")
            
            final_text = "\n".join(results)
            if len(final_text) > 8000:
                print(f"⚠️ [Qdrant DB] Truncating final RAG context from {len(final_text)} to 8000 characters to fit context window budget.")
                final_text = final_text[:8000] + "\n...[Remaining document context truncated to fit context budget]"
                
            return final_text + (
                "\n\n[CRITICAL RAG DIRECTIVE]:\n"
                "1. Ground your response STRICTLY in the provided document excerpts above.\n"
                "2. Cite references where possible using their page numbers and source filenames.\n"
                "3. If the excerpts do not contain the answer, state clearly that you could not find the information in the uploaded documents. DO NOT make up facts or extrapolate beyond the provided text."
            )
        except Exception as e:
            print(f"❌ [Qdrant DB] Error during search: {e}")
            return f"Error searching documents: {e}"
            
    return document_search_tool
