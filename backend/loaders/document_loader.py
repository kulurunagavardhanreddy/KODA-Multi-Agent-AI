# document_loader.py

import os
import base64
import functools
import hashlib
# Heavy imports deferred inside functions
from backend.database.chat_database import is_file_uploaded, log_uploaded_file, clear_all_uploaded_file_records

os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Define the central backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
local_models_path = os.path.join(backend_dir, "model")
os.makedirs(local_models_path, exist_ok=True)

# Force HuggingFace to use this local directory
os.environ["HF_HOME"] = local_models_path

_shared_qdrant_client = None

def get_shared_qdrant_client():
    global _shared_qdrant_client
    if _shared_qdrant_client is None:
        from qdrant_client import QdrantClient
        try:
            from backend.config import QDRANT_MODE, QDRANT_URL, QDRANT_API_KEY, QDRANT_HOST, QDRANT_PORT
        except ImportError:
            from ..config import QDRANT_MODE, QDRANT_URL, QDRANT_API_KEY, QDRANT_HOST, QDRANT_PORT
            
        qdrant_mode = QDRANT_MODE.lower().strip() if QDRANT_MODE else "local"
        
        if qdrant_mode == "local":
            qdrant_path = os.path.join(os.path.dirname(backend_dir), "qdrant_db")
            _shared_qdrant_client = QdrantClient(path=qdrant_path)
            print(f"📡 [Qdrant Client] Running in local offline mode (Path: {qdrant_path})")
        else:
            qdrant_url = QDRANT_URL
            qdrant_api_key = QDRANT_API_KEY
            qdrant_host = QDRANT_HOST
            qdrant_port = QDRANT_PORT
            
            if qdrant_url:
                _shared_qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
                print(f"📡 [Qdrant Client] Connecting to remote Qdrant server via URL: {qdrant_url}")
            elif qdrant_host:
                port_val = int(qdrant_port) if qdrant_port else 6333
                _shared_qdrant_client = QdrantClient(host=qdrant_host, port=port_val, api_key=qdrant_api_key)
                print(f"📡 [Qdrant Client] Connecting to remote Qdrant host: {qdrant_host}:{port_val}")
            else:
                # Fallback to local if configuration is missing
                qdrant_path = os.path.join(os.path.dirname(backend_dir), "qdrant_db")
                _shared_qdrant_client = QdrantClient(path=qdrant_path)
                print("⚠️ [Qdrant Client] Remote mode configured but URL/Host details are missing. Falling back to local offline mode.")
    return _shared_qdrant_client

@functools.lru_cache(maxsize=1)
def get_vector_store():
    """Initializes the local Qdrant DB and Local HuggingFace Embeddings."""
    from huggingface_hub import snapshot_download
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client.http.models import Distance, VectorParams
    
    client = get_shared_qdrant_client()
    
    specific_model_path = os.path.join(local_models_path, "all-MiniLM-L6-v2")
    
    if not os.path.exists(specific_model_path) or not os.listdir(specific_model_path):
        print("\n📥 Downloading AI model to local 'backend/model' directory for the first time...")
        snapshot_download(
            repo_id="sentence-transformers/all-MiniLM-L6-v2",
            local_dir=specific_model_path,
            local_dir_use_symlinks=False
        )

    embeddings = HuggingFaceEmbeddings(model_name=specific_model_path)
    
    collection_name = "uploaded_docs"
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    
    return QdrantVectorStore(client=client, collection_name=collection_name, embedding=embeddings)

@functools.lru_cache(maxsize=1)
def get_memory_vector_store():
    """Initializes the local Qdrant DB dedicated specifically to conversation memories."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client.http.models import Distance, VectorParams
    
    client = get_shared_qdrant_client()
    
    specific_model_path = os.path.join(local_models_path, "all-MiniLM-L6-v2")
    embeddings = HuggingFaceEmbeddings(model_name=specific_model_path)
    
    collection_name = "conversation_memories"
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
    
    return QdrantVectorStore(client=client, collection_name=collection_name, embedding=embeddings)

def get_file_hash(file_path: str) -> str:
    """Calculates the SHA-256 hash of a file to detect duplicates."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def extract_document_image(file_path: str) -> str:
    """Extracts the first page of a PDF as a high-res base64 image."""
    if not file_path.lower().endswith(".pdf"):
        return None
        
    try:
        import fitz  # type: ignore # PyMuPDF
        with fitz.open(file_path) as doc:
            if len(doc) > 0:
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img_bytes = pix.tobytes("jpeg")
                return f"data:image/jpeg;base64,{base64.b64encode(img_bytes).decode('utf-8')}"
    except ImportError:
        print("⚠️ PyMuPDF not found. Please run 'pip install pymupdf' to enable PDF Vision.")
    except Exception as e:
        print(f"⚠️ PDF Vision Extraction Error: {e}")
    return None

def clean_extracted_text(text: str) -> str:
    """Cleans extracted PDF/docx text by resolving ligatures, normalization, and line break spacing."""
    if not text:
        return ""
    import re
    # 1. Normalize ligatures (very common PDF extraction issue)
    ligatures = {
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "ﬅ": "ft",
        "ﬆ": "st"
    }
    for lig, repl in ligatures.items():
        text = text.replace(lig, repl)
        
    # 2. Fix broken hyphenated line breaks (e.g., "deve- \nlopment" -> "development")
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    
    # 3. Clean up excessive spacing and normalize line breaks
    text = re.sub(r'[ \t]+', ' ', text)  # normalize horizontal spaces
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)  # max 2 consecutive newlines
    
    return text.strip()

def is_file_in_qdrant(user_id: str, file_name: str) -> bool:
    """Verifies if the vectors for the given file exist in Qdrant."""
    try:
        from qdrant_client.http import models
        client = get_shared_qdrant_client()
        collection_name = "uploaded_docs"
        
        result = client.count(
            collection_name=collection_name,
            count_filter=models.Filter(
                must=[
                    models.FieldCondition(key="metadata.filename", match=models.MatchValue(value=file_name)),
                    models.FieldCondition(key="metadata.owner", match=models.MatchValue(value=user_id))
                ]
            )
        )
        return result.count > 0
    except Exception as e:
        print(f"⚠️ [Qdrant DB] Error checking file existence: {e}")
        return False

def process_and_store_document(file_path: str, user_id: str = "", session_id: str = "") -> str:
    """Splits a document into chunks, embeds them, and stores them in Qdrant."""
    from langchain_community.document_loaders import PyPDFLoader, TextLoader, Docx2txtLoader, UnstructuredFileLoader, CSVLoader, UnstructuredExcelLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    TOTAL_STAGES = 3
    is_guest = user_id.startswith("guest_")
    
    print(f"\n📄 [1/{TOTAL_STAGES}] Reading and extracting: {file_path}...")
    
    file_hash = get_file_hash(file_path)
    file_name = os.path.basename(file_path)
    
    if not is_guest and is_file_uploaded(user_id, file_hash) and is_file_in_qdrant(user_id, file_name):
        print(f"⏭️  [Skip] Content match found and vectors exist for '{file_name}'.")
        return f"The file '{file_name}' already exists in your vault. (Skipped duplicate)"

    ext = file_path.lower()
    try:
        if ext.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        elif ext.endswith(".txt"):
            loader = TextLoader(file_path)
        elif ext.endswith(".docx"):
            loader = Docx2txtLoader(file_path)
        elif ext.endswith(".csv"):
            loader = CSVLoader(file_path, encoding="utf-8")
        elif ext.endswith((".xls", ".xlsx")):
            loader = UnstructuredExcelLoader(file_path)
        elif ext.endswith((".jpg", ".jpeg", ".png", ".bmp")):
            loader = UnstructuredFileLoader(file_path)
        else:
            loader = UnstructuredFileLoader(file_path)
            
        documents = loader.load()
        # Clean text to remove ligatures, excessive spaces, and formatting issues
        for doc in documents:
            if doc.page_content:
                doc.page_content = clean_extracted_text(doc.page_content)
    except Exception as e:
        print(f"⚠️ [Loader Warning] Could not parse text from {file_name}. Storing as reference only. Error: {e}")
        documents = []

    if documents:
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=2500, chunk_overlap=250)
        chunks = text_splitter.split_documents(documents)
    else:
        chunks = []
    
    for i, chunk in enumerate(chunks):
        chunk.metadata["owner"] = user_id
        if session_id:
            chunk.metadata["session_id"] = session_id
        
        # Rich Metadata Extraction
        chunk.metadata["filename"] = file_name
        chunk.metadata["document_type"] = ext.split(".")[-1] if "." in ext else "unknown"
        chunk.metadata["chunk_id"] = i
        chunk.metadata["total_chunks"] = len(chunks)
        if "page" in chunk.metadata:
            try:
                chunk.metadata["page"] = int(chunk.metadata["page"])
            except:
                pass
        
    print(f"✂️  [2/{TOTAL_STAGES}] Processing Complete: Created {len(chunks)} segments.")
    print(f"🔄 [3/{TOTAL_STAGES}] Attempting to save to Qdrant DB...")
    
    try:
        if chunks:
            vector_store = get_vector_store()
            vector_store.add_documents(chunks)
            print(f"✅ SUCCESS: {len(chunks)} segments safely stored!\n")
        else:
            print(f"ℹ️  Notice: File '{file_name}' logged via Hash, but no text extracted to embed.")

        if not is_guest:
            log_uploaded_file(user_id, file_hash, file_name)
        
        return f"Processed '{file_name}' successfully ({len(chunks)} chunks)."
        
    except Exception as e:
        print(f"❌ ERROR: Failed to sync with database.\nReason: {e}\n")
        raise Exception("Database Error: Failed to store file metadata.")
