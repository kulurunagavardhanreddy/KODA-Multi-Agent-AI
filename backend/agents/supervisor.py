# supervisor.py

import os
import re
import json
import time
import base64
import asyncio
import logging
import requests
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

try:
    from backend.config import GEMINI_API_KEY
    from backend.providers import get_provider
    from backend.prompts.system_prompts import get_koda_system_prompt
    from backend.prompts.agent_prompts import get_critic_system_prompt
    from backend.memory.conversation_memory import build_history_context, compress_and_save_memories_bg
    from .intent_router import is_tool_execution_plan, parse_execution_plan
except ImportError:
    from ..config import GEMINI_API_KEY
    from ..providers import get_provider
    from ..prompts.system_prompts import get_koda_system_prompt
    from ..prompts.agent_prompts import get_critic_system_prompt
    from ..memory.conversation_memory import build_history_context, compress_and_save_memories_bg
    from .intent_router import is_tool_execution_plan, parse_execution_plan

logger = logging.getLogger(__name__)

_provider = None
_llm = None

def _get_provider():
    global _provider
    if _provider is None:
        _provider = get_provider()
    return _provider

def _get_llm():
    global _llm
    if _llm is None:
        _llm = _get_provider().get_llm()
    return _llm

def classify_query_intent(query: str) -> str:
    """Classifies user query intent using lightweight structural signals only.
    
    This function only handles structural bypasses (greetings, memory recall cues).
    All other routing decisions — including identity, persona, hypothetical, opinion
    and tool selection — are delegated to the LLM brain via the system prompt.
    """
    if not query:
        return "GENERAL"
    q_clean = query.lower().strip()
    q_clean = re.sub(r"[?.!,;:]", "", q_clean).strip()
    
    # Fast-path: explicit greetings → skip memory & doc lookup, go straight to LLM
    greetings = [
        "hi", "hello", "hey", "greetings", "good morning", "good afternoon",
        "good evening", "howdy", "whats up", "sup", "yo", "hola", "namaste",
        "chanti", "koda"
    ]
    if q_clean in greetings or any(q_clean.startswith(g + " ") for g in greetings):
        return "GREETING"

    # Fast-path: obvious acknowledgements → skip memory & doc lookup
    thanks = ["thanks", "thank you", "thankyou", "awesome", "perfect", "cool", "great", "ok", "okay", "bye", "goodbye"]
    if q_clean in thanks or any(q_clean.startswith(t) for t in thanks):
        return "CONVERSATION"

    # Fast-path: memory recall questions → load long-term memory context
    memory_indicators = [
        "remember", "forget", "we discussed", "we talked", "last time", "past chat",
        "my preference", "who am i", "my name", "what is my", "what do i", "continue", "what did we"
    ]
    if any(ind in q_clean for ind in memory_indicators):
        return "MEMORY"

    # Everything else → let the LLM system prompt decide (GENERAL path)
    return "GENERAL"

def build_synth_prompt(sys_prompt_text: str) -> str:
    """Prepares clean base prompt for response synthesis by stripping tool list and routing rules."""
    # 1. Strip AVAILABLE TOOLS block so LLM does not see tool schemas during synthesis
    tools_start = sys_prompt_text.find("AVAILABLE TOOLS:")
    routing_start = sys_prompt_text.find("CRITICAL ROUTING RULES:")
    if tools_start != -1 and routing_start != -1:
        sys_prompt_text = sys_prompt_text[:tools_start] + sys_prompt_text[routing_start:]
    
    # 2. Strip CRITICAL ROUTING RULES block (routing is already finished)
    routing_start = sys_prompt_text.find("CRITICAL ROUTING RULES:")
    assistant_start = sys_prompt_text.find("CRITICAL ASSISTANT RULES")
    if routing_start != -1 and assistant_start != -1:
        sys_prompt_text = sys_prompt_text[:routing_start] + sys_prompt_text[assistant_start:]

    return sys_prompt_text

def clean_llm_output(text: str) -> str:
    """Dynamically removes internal monologues, role prefixes (Chitti, Reddy), raw JSON tool arrays/calls, XML tags, and raw function calls from LLM outputs."""
    if not text:
        return ""
    import re
    # 1. Remove reasoning/thinking/tool XML blocks
    text = re.sub(r'<(?:antThinking|tool_code|thinking|plan|reasoning)>.*?</(?:antThinking|tool_code|thinking|plan|reasoning)>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'^\s*<(?:antThinking|tool_code|thinking|plan|reasoning)>', '', text, flags=re.IGNORECASE)
    
    # 2. Remove role headers and internal monologues (e.g. "Chitti", "Reddy", "The user wants me to analyze...")
    text = re.sub(r'(?:^|\n)(?:Chitti|Reddy|Assistant|System|User|Planner):\s*', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:^|\n)(?:Chitti|Reddy)\b[^\n]*\n', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:^|\n)(?:The user wants me to|Let me explore|Let me read|I will check|I will inspect|The user said)[^\n]*\n?', '\n', text, flags=re.IGNORECASE)
    
    # 3. Remove raw JSON execution plan blocks & raw JSON tool arrays/objects inside code fences
    text = re.sub(r'```(?:json)?\s*\[\s*\{.*?"(?:name|tool|tool_name)"\s*:.*?\}\s*\]\s*```', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'```(?:json)?\s*\{.*?"(?:plan|tool|tool_name|name)"\s*:.*?\}\s*```', '', text, flags=re.IGNORECASE | re.DOTALL)
    
    # 4. Remove raw JSON tool call objects/arrays (unfenced)
    text = re.sub(r'\[\s*\{\s*"(?:name|tool|tool_name)"\s*:\s*".*?"\s*,.*?\n?\s*\}\s*\]', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\{\s*"(?:name|tool|tool_name)"\s*:\s*"[^"]+"\s*,\s*"(?:arguments|tool_args|params)"\s*:\s*\{.*?\}\s*\}', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'^\s*\{.*?"(?:plan|tool_calls)"\s*:\s*\[.*?\].*?\}\s*$', '', text, flags=re.IGNORECASE | re.DOTALL)

    # 5. Check if entire text is a single JSON object with tool/plan keys
    stripped = text.strip()
    if (stripped.startswith("{") or stripped.startswith("[")) and (stripped.endswith("}") or stripped.endswith("]")):
        lower_str = stripped.lower()
        if any(k in lower_str for k in ['"name"', '"tool"', '"tool_name"', '"arguments"', '"tool_args"', '"plan"']) and any(t in lower_str for t in ['_tool', 'mcp_', 'search', 'calculator', 'distance', 'query', 'action']):
            return ""
            
    # 6. Remove raw function call syntax lines and print tool calls
    text = re.sub(r'(?:print\s*\(\s*)?[a-zA-Z0-9_]+_tool[a-zA-Z0-9_]*\s*\([^\)]*\)(?:\s*\))?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?:print\s*\(\s*)?mcp_[a-zA-Z0-9_]+\s*\([^\)]*\)(?:\s*\))?', '', text, flags=re.IGNORECASE)
    
    return text.strip()

def sanitize_history_messages(history_list):
    """Filters out raw Python tool calls, JSON plans, XML reasoning tags, and temporary planning status updates from the chat history context."""
    sanitized = []
    for msg in history_list:
        if msg.__class__.__name__ == "AIMessage" and msg.content:
            cleaned_content = clean_llm_output(msg.content)
            # Only keep the message if it still contains conversational content
            if cleaned_content:
                msg_copy = msg.__class__(content=cleaned_content)
                sanitized.append(msg_copy)
        else:
            sanitized.append(msg)
    return sanitized

def __getattr__(name: str):
    if name == "llm":
        return _get_llm()
    if name == "provider":
        return _get_provider()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
MISTRAL_API_BASE = os.getenv("MISTRAL_API_BASE", "http://164.52.199.204/v1")
class StreamingCleaner:
    def __init__(self):
        self.buffer = ""
        self.in_block = False
        self.block_tag = ""
        self.tags = ["thinking", "antthinking", "tool_code", "plan", "reasoning"]
        self.first_chunk = True
        self.suppress_json_stream = False

    def process_chunk(self, chunk: str) -> str:
        self.buffer += chunk
        
        if self.suppress_json_stream:
            self.buffer = ""
            return ""

        # 1. On initial chunks, detect if the LLM is attempting to output a raw JSON tool call / plan
        if self.first_chunk:
            stripped = self.buffer.lstrip()
            if not stripped:
                return ""
            # If it starts with JSON structural tokens, wait to see if it's a tool call JSON
            if stripped.startswith("{") or stripped.startswith("[") or stripped.startswith("```"):
                if len(self.buffer) < 120 and "\n" not in self.buffer and not (self.buffer.rstrip().endswith("}") or self.buffer.rstrip().endswith("]")):
                    return ""
                cleaned = clean_llm_output(self.buffer)
                if not cleaned or (cleaned.startswith("{") and ("\"name\"" in cleaned or "\"tool\"" in cleaned)):
                    # It was a raw JSON tool call! Suppress all further chunks from this stream
                    self.suppress_json_stream = True
                    self.buffer = ""
                    self.first_chunk = False
                    return ""
            else:
                if len(self.buffer) < 80 and "\n" not in self.buffer:
                    return ""
                self.buffer = clean_llm_output(self.buffer)
                self.first_chunk = False

        if self.suppress_json_stream:
            self.buffer = ""
            return ""

        # Continually scrub any embedded XML blocks or role headers
        output = ""
        while self.buffer:
            if not self.in_block:
                found_tag = None
                found_idx = -1
                for tag in self.tags:
                    idx = self.buffer.lower().find(f"<{tag}")
                    if idx != -1 and (found_idx == -1 or idx < found_idx):
                        found_idx = idx
                        found_tag = tag
                
                if found_tag:
                    output += self.buffer[:found_idx]
                    self.buffer = self.buffer[found_idx:]
                    gt_idx = self.buffer.find(">")
                    if gt_idx != -1:
                        self.in_block = True
                        self.block_tag = found_tag
                        self.buffer = self.buffer[gt_idx+1:]
                    else:
                        break
                else:
                    lt_idx = self.buffer.rfind("<")
                    if lt_idx != -1:
                        possible_tag = self.buffer[lt_idx:].lower()
                        is_possible = False
                        for tag in self.tags:
                            if f"<{tag}".startswith(possible_tag) or possible_tag.startswith(f"<{tag}"):
                                is_possible = True
                                break
                        if is_possible:
                            output += self.buffer[:lt_idx]
                            self.buffer = self.buffer[lt_idx:]
                            break
                    
                    output += self.buffer
                    self.buffer = ""
            else:
                closing_tag = f"</{self.block_tag}>"
                close_idx = self.buffer.lower().find(closing_tag)
                if close_idx != -1:
                    self.in_block = False
                    self.block_tag = ""
                    self.buffer = self.buffer[close_idx + len(closing_tag):]
                else:
                    slash_idx = self.buffer.rfind("</")
                    if slash_idx != -1:
                        if closing_tag.startswith(self.buffer[slash_idx:].lower()):
                            self.buffer = self.buffer[slash_idx:]
                            break
                    self.buffer = ""
                    break
        
        return output

    def flush(self) -> str:
        if self.suppress_json_stream:
            self.buffer = ""
            return ""
        if self.first_chunk:
            cleaned = clean_llm_output(self.buffer)
            self.buffer = ""
            self.first_chunk = False
            return cleaned
        output = self.buffer
        self.buffer = ""
        return clean_llm_output(output)

class AdaptiveStreamBuffer:
    """Adaptive Producer Buffer: Batches cleaned tokens into character threshold (60 chars) or time threshold (100ms) chunks before yielding over SSE."""
    def __init__(self, cleaner, max_chars: int = 60, max_delay_sec: float = 0.10):
        self.cleaner = cleaner
        self.max_chars = max_chars
        self.max_delay_sec = max_delay_sec

    async def wrap(self, async_stream):
        buffer = ""
        last_flush = time.time()
        
        async for chunk in async_stream:
            if not chunk.content:
                continue
            cleaned = self.cleaner.process_chunk(chunk.content)
            if not cleaned:
                continue
            
            buffer += cleaned
            now = time.time()
            if len(buffer) >= self.max_chars or (now - last_flush) >= self.max_delay_sec:
                yield buffer
                buffer = ""
                last_flush = now
                
        flushed = self.cleaner.flush()
        if flushed:
            buffer += flushed
        if buffer:
            yield buffer

class ToolStep(BaseModel):
    step: int = 1
    tool: str
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    depends_on: Optional[List[int]] = None
    task: Optional[str] = None

async def chat_with_agent(conversation_history: list, user_location: str = "", user_id: str = "", image_b64: str = "", session_id: str = ""):
    """Asynchronously passes history to the AI and streams the response back token-by-token."""
    try:
        from backend.config import USE_LANGGRAPH_ENGINE
        if USE_LANGGRAPH_ENGINE:
            from backend.agents.langgraph_supervisor import chat_with_langgraph
            async for item in chat_with_langgraph(conversation_history, user_location, user_id, image_b64, session_id):
                yield item
            return
    except Exception as lg_err:
        logger.warning(f"⚠️ [LangGraph Engine] Falling back to procedural supervisor: {lg_err}")

    yielded_any = False
    workflow_state = ""
    yield {"status": "Initializing agent workspace..."}
    
    # 1. Fetch dynamic tools isolated by user
    from backend.tools import get_agent_tools
    tools = get_agent_tools(user_id)
    tool_dict = {t.name: t for t in tools}
    tool_descriptions = "\n".join([f"- {t.name} (Args schema: {list(t.args.keys())}): {t.description}" for t in tools])

    user_latest_query = ""
    for msg in reversed(conversation_history):
        if isinstance(msg, HumanMessage):
            user_latest_query = msg.content if isinstance(msg.content, str) else str(msg.content[0].get("text", ""))
            break

    TOOL_UX_MAP = {
        "web_search_tool": {"emoji": "🌐", "text": "Searching web"},
        "python_repl_tool": {"emoji": "🐍", "text": "Running calculations"},
        "document_search_tool": {"emoji": "📄", "text": "Searching documents"},
        "route_distance_tool": {"emoji": "🗺️", "text": "Calculating route"},
        "local_places_tool": {"emoji": "🏪", "text": "Finding local places"},
        "product_search_tool": {"emoji": "🛍️", "text": "Searching for products"}
    }

    current_system_time = time.strftime("%A, %B %d, %Y | Current Time: %I:%M %p")
    
    # 2. Resolve GPS to City Name
    location_context = ""
    if user_location:
        yield {"status": "Resolving GPS location..."}
        resolved_location = user_location
        try:
            if "," in user_location:
                lat, lon = [c.strip() for c in user_location.split(',')]
                headers = {'User-Agent': 'NexaFetchBot/1.0'}
                url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
                resp = requests.get(url, headers=headers, timeout=4)
                if resp.status_code == 200:
                    data = resp.json()
                    if "display_name" in data:
                        resolved_location = data["display_name"]
                    else:
                        addr = data.get("address", {})
                        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb") or addr.get("county")
                        state = addr.get("state", "")
                        if city:
                            resolved_location = f"{city}, {state}".strip(", ")
        except Exception as e:
            logger.warning("⚠️ [Geocoding] Failed: %s", e)

        user_maps_link = f"https://www.google.com/maps/dir/?api=1&destination={user_location}&travelmode=driving&dir_action=navigate"
        lat, lon = [c.strip() for c in user_location.split(',')] if "," in user_location else ("0", "0")
        static_map_url = f"https://static-maps.yandex.ru/1.x/?lang=en_US&ll={lon},{lat}&z=14&l=map&size=400,180&pt={lon},{lat},pm2rdl"
        safe_loc = resolved_location.replace('"', '&quot;').replace("'", "&#39;")
        
        html_card = f"""
  <div class="koda-map-card" onclick="window.open('{user_maps_link}', '_blank')">
    <div class="map-preview">
      <img src="{static_map_url}" alt="Location Preview">
      <div class="status-badge">Current Location</div>
    </div>
    <div class="card-content">
      <div class="location-info">
        <div class="dot-indicator"></div>
        <div class="text-block">
          <h3>{safe_loc}</h3>
          <p>Your Exact GPS Location</p>
        </div>
      </div>
      <div class="nav-button">Open Maps <span class="arrow">→</span></div>
    </div>
  </div>
"""
        # Check if the user specifically asked for coordinates/map
        user_asked_for_map = False
        if user_latest_query:
            lower_q = user_latest_query.lower()
            if any(kw in lower_q for kw in ["location", "map", "gps", "where am i", "coordinates", "koilkuntla", "distance"]):
                user_asked_for_map = True

        if user_asked_for_map:
            location_context = (
                f"USER BACKGROUND INFO: The user's exact GPS coordinates are {user_location} (Latitude,Longitude). "
                f"This dynamically resolves to the address: '{resolved_location}'.\n"
                f"If the user asks for their location, a map, or a link to their location, you MUST output this EXACT HTML block to display their premium location card. Do NOT wrap it in code backticks:\n{html_card}\n\n"
                "DO NOT mention or volunteer this location during casual conversation or general greetings."
            )
        else:
            location_context = (
                f"USER BACKGROUND INFO: The user's location resolves to: '{resolved_location}'. "
                "Do NOT output any map HTML block, location cards, or GPS visual components, as they are not requested. "
                "Only answer questions regarding location in plain conversational text."
            )
    else:
        location_context = "USER BACKGROUND INFO: The user's GPS location is empty."

    # 3. Load Long-term Memory summaries using Intent Routing
    from backend.database.chat_database import get_session_memories
    from backend.memory.vector_memory import search_conversation_memories
    
    intent = classify_query_intent(user_latest_query) if user_latest_query else "GENERAL"
    logger.info("🧭 [Intent Router] Classified user query intent: '%s'", intent)
    logger.info("📥 [USER QUERY]: %s", user_latest_query)
    logger.info("🧭 [INTENT]: %s", intent)

    if intent in ["GREETING", "CONVERSATION"]:
        logger.info("🎯 [ROUTER] Direct response — Greeting/Smalltalk bypass")
        yield f"<div class='hidden-sources' style='display:none;' data-sources=''></div>"

        provider_id = _get_provider().__class__.__name__.replace("Provider", "")
        sys_prompt = get_koda_system_prompt(current_system_time, "", "", "", tool_descriptions, provider_id)
        langchain_messages = [SystemMessage(content=sys_prompt)]
        safe_history = sanitize_history_messages(build_history_context(conversation_history, image_b64))
        langchain_messages.extend(safe_history)

        cleaner = StreamingCleaner()
        async for chunk in _get_llm().astream(langchain_messages):
            if chunk.content:
                cleaned_chunk = cleaner.process_chunk(chunk.content)
                if cleaned_chunk:
                    yield cleaned_chunk
        flushed = cleaner.flush()
        if flushed:
            yield flushed
        return

    yield {"status": "Retrieving session memories..."}

    existing_summary = ""
    semantic_memories = ""

    if session_id:
        try: 
            existing_summary = get_session_memories(user_id, session_id)
            if existing_summary: logger.info("🧠 [Memory Vault] Loaded granular memories for session %s...", session_id[:8])
        except: pass
        
    if user_latest_query and user_id:
        try:
            semantic_memories = search_conversation_memories(user_id, user_latest_query)
            if semantic_memories: logger.info("🧠 [Semantic Search] Retrieved cross-session memories for user...")
        except: pass
        
    summary_context = ""
    if existing_summary or semantic_memories:
        summary_context = "\nLONG-TERM MEMORY VAULT:\n"
        if existing_summary: summary_context += f"--- Current Session Topics ---\n{existing_summary}\n"
        if semantic_memories: summary_context += f"--- Semantically Relevant Past Memories ---\n{semantic_memories}\n"

    # 3. Retrieve user's vault documents for pre-routing awareness
    from backend.database.chat_database import get_user_uploaded_files
    user_files = get_user_uploaded_files(user_id) if user_id else []
    
    # Pre-routing check: If the query matches any document in Qdrant with high similarity,
    # we bypass the planning/router LLM call completely to maximize speed and guarantee correct intent.
    bypass_planning = False
    rag_context = ""
    
    if user_id and user_latest_query and intent not in ["GREETING", "CONVERSATION"]:
        yield {"status": "Searching document vault..."}
        try:
            from backend.loaders.document_loader import get_vector_store
            from qdrant_client.http import models
            
            vector_store = get_vector_store()
            qdrant_filter = models.Filter(
                must=[models.FieldCondition(key="metadata.owner", match=models.MatchValue(value=user_id))]
            )
            # Run similarity search with score
            docs_with_scores = vector_store.similarity_search_with_score(user_latest_query, k=3, filter=qdrant_filter)
            
            # Cosine similarity score threshold (0.55 is a robust limit in normalized Qdrant embeddings)
            SIMILARITY_THRESHOLD = 0.55
            has_relevant_doc = False
            
            for doc, score in docs_with_scores:
                logger.info("🔍 [Vault] Score: %.4f | File: %s", score, doc.metadata.get('filename'))
                if score >= SIMILARITY_THRESHOLD:
                    has_relevant_doc = True
                    
            if has_relevant_doc:
                logger.info("🎯 [ROUTER] Document match (score >= %.2f) — bypassing planner, running RAG", SIMILARITY_THRESHOLD)
                logger.info("🎯 [Vault Pre-routing] Relevant vault documents matched (score >= %.2f). Bypassing planning phase!", SIMILARITY_THRESHOLD)
                
                # Fetch RAG context using neighbor expansion and merging pipeline
                from backend.workflows.rag_workflow import run_rag_search
                yield {"status": "Synthesizing answer from documents..."}
                rag_context = run_rag_search(user_latest_query, user_id)
                bypass_planning = True
        except Exception as pre_err:
            logger.warning("⚠️ [Vault Pre-routing] Fast vector check failed, falling back to LLM router: %s", pre_err)

    # 4. Load Active Project Workspace context from SQLite database
    from backend.database.chat_database import get_active_user_workspace
    active_ws = get_active_user_workspace(user_id) if user_id else None
    active_ws_forward = active_ws.replace('\\', '/') if active_ws else "uploads"
        
    workspace_context = (
        f"ACTIVE PROJECT WORKSPACE: The user's currently active project directory is '{active_ws_forward}'. "
        "You have full, active read and write access to all files, scripts, and folders inside this directory via the `mcp_filesystem_` tools (like list_directory, read_file, search_nodes). "
        "If the user asks to read, analyze, summarize, inspect, search, or review the project, files, codebases, or directories, you MUST use the `mcp_filesystem_` tools to locate and read them.\n"
        "CRITICAL MARKDOWN FILE LINKING RULES:\n"
        "Whenever discussing, outputting, or explaining files, directories, or classes/functions in the project, you MUST format them as clickable absolute system paths using forward slashes (even on Windows). "
        "You must prefix the exact file path from the workspace. Examples using the active workspace:\n"
        f"- To link a root file: [filename.py](file:///{active_ws_forward}/filename.py)\n"
        f"- To link a nested file: [filename.py](file:///{active_ws_forward}/backend/agents/supervisor.py)\n"
        "Ensure the links are active absolute file urls starting with file:/// followed by the absolute path."
    )

    # 5. Generate the main system prompt using current active provider identification
    provider_id = _get_provider().__class__.__name__.replace("Provider", "")
    sys_prompt = get_koda_system_prompt(current_system_time, location_context, summary_context, workspace_context, tool_descriptions, provider_id)
    
    langchain_messages = [SystemMessage(content=sys_prompt)]

    safe_history = sanitize_history_messages(build_history_context(conversation_history, image_b64))
    langchain_messages.extend(safe_history)
    if bypass_planning:
        try:
            logger.info("🧠 Synthesizing direct response from RAG context...")
            synth_base_prompt = build_synth_prompt(sys_prompt)
                
            workflow_state = f"--- STEP 1 (document_search_tool) RESULT ---\n{rag_context}\n\n"
            synth_sys_content = (
                "🚨 CRITICAL MODE: YOU ARE IN FINAL RESPONSE SYNTHESIS MODE.\n"
                "ALL REQUIRED TOOLS HAVE ALREADY BEEN EXECUTED BY THE SYSTEM. THEIR OUTPUT DATA IS PROVIDED IN THE 'PIPELINE EXECUTION DATA' SECTION BELOW.\n"
                "DO NOT OUTPUT ANY JSON, DO NOT OUTPUT TOOL CALLS, DO NOT OUTPUT FUNCTION PAYLOADS LIKE `{\"name\": ...}`.\n"
                "YOU MUST RESPOND DIRECTLY TO THE USER IN CLEAN CONVERSATIONAL MARKDOWN USING THE RETRIEVED DATA.\n\n"
                + synth_base_prompt
                + f"\n\n--- PIPELINE EXECUTION DATA ---\n{rag_context}\n\nFINAL INSTRUCTION:\n"
                "1. The required tools have ALREADY been executed and their outputs are provided in the PIPELINE EXECUTION DATA section above. Do NOT say 'I will read', 'I will inspect', 'Let me check', 'I need to open', or describe future actions. Answer immediately using the supplied tool outputs.\n"
                "2. Extract ONLY the exact facts needed, BUT ALWAYS provide the direct Source URLs (as clickable Markdown links) if offering bookings, products, or external references. IF THE DATA DOES NOT CONTAIN THE ANSWER, DO NOT HALLUCINATE OR MAKE UP NUMBERS. State clearly that you could not find the information.\n"
                "3. DO NOT output raw Python code, developer logs, raw scraped web text, or any internal reasoning XML tags (such as <antThinking>, <tool_code>, or <thinking>). Never output raw print(mcp_...) tool calls, raw JSON tool payloads, or execution plans. Output ONLY the clean user-facing Markdown answer.\n"
                "4. NEVER copy-paste massive blocks of text, website navigation, or footers.\n"
                "5. DO NOT generate a JSON execution plan. If a tool failed, inform the user naturally in plain text.\n"
                "6. Once you have provided the final answer, wrap exactly 3 to 4 follow-up questions total inside <followup> and </followup> tags at the very end of your response, with each option on a new line starting with a hyphen. Do not add any extra text or headers. STOP generating immediately after the closing tag.\n"
                "7. SENIOR-LEVEL ENGINEERING REASONING: If analyzing technical files, resumes, or codebases, infer core engineering concepts and explain how details (like SKIP LOCKED, WebSockets, or async pipelines) map to microservices, concurrency, distributed queues, and fault tolerance. Reason like a Senior Architect rather than a simple document summarizer.\n"
                "8. FACTUAL GROUNDING: Differentiate clearly between established facts, reasonable inferences, suggestions, and illustrative hypothetical examples. Do not blur these categories, and never present assumptions or estimates as verified facts."
            )
            
            synth_messages = [SystemMessage(content=synth_sys_content)] + safe_history
            
            # Print synthesis prompt log safely (encoding as ascii to prevent Windows CP1252 crash)
            logger.info("🚀 [LLM] Running RAG direct synthesis (%d messages)", len(synth_messages))
            
            first_token_yielded = False
            all_sources = ["Uploaded Document"]
            cleaner = StreamingCleaner()
            
            async for chunk in _get_llm().astream(synth_messages):
                if chunk.content:
                    if not first_token_yielded:
                        first_token_yielded = True
                        if all_sources:
                            sources_json = json.dumps(all_sources)
                            sources_b64 = base64.b64encode(sources_json.encode('utf-8')).decode('utf-8')
                            yield f"<div class='hidden-sources' style='display:none;' data-sources='{sources_b64}'></div>"
                    
                    cleaned_chunk = cleaner.process_chunk(chunk.content)
                    if cleaned_chunk:
                        yield cleaned_chunk
            flushed = cleaner.flush()
            if flushed:
                yield flushed
            return
        except Exception as e:
            logger.error("❌ Direct synthesis failed, falling back to full planner: %s", e)

    try:
        logger.info("🧭 [Router] Analyzing intent...")
        yield {"status": "Analyzing request intent..."}
        is_chat_only = False
        is_json_plan = False
        plan_buffer = ""
        stream_started = False
        cleaner = StreamingCleaner()

        # Run planner LLM. We buffer the first few tokens to check if it's a JSON plan.
        async for chunk in _get_llm().astream(langchain_messages):
            if chunk.content:
                plan_buffer += chunk.content
                
                if not stream_started:
                    stripped = plan_buffer.lstrip()
                    
                    # If it starts with JSON indicators, keep buffering silently
                    if stripped.startswith("{") or stripped.startswith("[") or stripped.startswith("```"):
                        continue
                    
                    # If it's short, check if it could be a tool plan
                    if len(stripped) < 80:
                        lower_strip = stripped.lower()
                        if any(k in lower_strip for k in ['"plan"', '"tool"', '"tool_name"', '"tool_calls"', '"arguments"', '"tool_args"', '"path"', '"paths"', '"query"', 'mcp_']):
                            continue
                        if re.search(r'(?:print\s*\(\s*)?[a-zA-Z0-9_]+_tool[a-zA-Z0-9_]*\s*\(', stripped) or re.search(r'(?:print\s*\(\s*)?mcp_[a-zA-Z0-9_]*\s*\(', stripped):
                            continue
                    
                    # Not a tool plan, start streaming immediately!
                    stream_started = True
                    yield f"<div class='hidden-sources' style='display:none;' data-sources=''></div>"
                    cleaned_chunk = cleaner.process_chunk(plan_buffer)
                    if cleaned_chunk:
                        yield cleaned_chunk
                else:
                    # In streaming mode, clean and yield chunk immediately
                    cleaned_chunk = cleaner.process_chunk(chunk.content)
                    if cleaned_chunk:
                        yield cleaned_chunk

        if stream_started:
            flushed = cleaner.flush()
            if flushed:
                yield flushed

        # Check if we need to process as JSON plan or direct chat
        if not stream_started:
            stripped_buf = plan_buffer.strip()
            lower_buf = stripped_buf.lower()
            has_tool_call = False
            
            from backend.agents.intent_router import is_tool_execution_plan
            if is_tool_execution_plan(stripped_buf):
                has_tool_call = True
            elif ("{" in stripped_buf or "[" in stripped_buf or "```" in stripped_buf) and any(
                k in lower_buf for k in [
                    '"plan"', '"tool"', '"tool_name"', '"tool_calls"', '"arguments"',
                    '"tool_args"', '"path"', '"paths"', '"query"', '"action"', 'mcp_'
                ]
            ):
                has_tool_call = True
            elif re.search(r'mcp_[a-zA-Z0-9_]+\s*\(', stripped_buf) or re.search(r'[a-zA-Z0-9_]+_tool[a-zA-Z0-9_]*\s*\(', stripped_buf):
                has_tool_call = True
                
            if has_tool_call:
                is_json_plan = True
                logger.info("🧭 [Router] Tool Execution Plan detected in planner buffer.")
                yield {"status": "Routing task & preparing tools..."}
            else:
                # ✅ IMPORTANT: The plan_buffer here may contain a partial JSON plan that
                # clean_llm_output() could not fully strip. NEVER yield plan_buffer directly.
                # Instead, re-call the LLM with a direct answer instruction to get a clean response.
                is_chat_only = True
                logger.info("🎯 [ROUTER] Direct response — conversational (re-synthesis)")
                logger.info("🎯 [Router] Casual Chat / Direct Answer — Re-synthesizing from LLM (not from plan_buffer).")
                yield f"<div class='hidden-sources' style='display:none;' data-sources=''></div>"
                # Re-call the LLM to get a clean conversational response
                direct_cleaner = StreamingCleaner()
                async for chunk in _get_llm().astream(langchain_messages):
                    if chunk.content:
                        cleaned = direct_cleaner.process_chunk(chunk.content)
                        if cleaned:
                            yield cleaned
                flushed2 = direct_cleaner.flush()
                if flushed2:
                    yield flushed2
                yielded_any = True
        else:
            is_chat_only = True
            yielded_any = True
            logger.info("🎯 [ROUTER] Direct response — streamed to UI")
            logger.info("🎯 [Router] Casual Chat / Direct Answer detected. (Streaming directly to UI)")

        if is_json_plan:
            plan = parse_execution_plan(plan_buffer)
            
            # Universal fallback if parsing failed completely
            if not plan:
                logger.warning("⚠️ [Planner] Failed to parse JSON plan, defaulting to web search.")
                fallback_query = user_latest_query if user_latest_query else "Search for information"
                fallback_tool = next((t.name for t in tools if "search" in t.name), tools[0].name if tools else None)
                plan = [{"step": 1, "tool": fallback_tool, "tool_args": {"query": fallback_query[:100]}}] if fallback_tool else []

            validated_plan = []
            for s in plan:
                try:
                    if isinstance(s, dict) and "tool" in s:
                        valid_step = ToolStep(**s)
                        validated_plan.append(valid_step.model_dump())
                except Exception as ve:
                    logger.warning("⚠️ [Pydantic] Dropping malformed step: %s", ve)
            plan = validated_plan

            logger.info("🎯 [ROUTER] Tool plan — %d step(s)", len(plan))
            for idx, step in enumerate(plan):
                logger.info("   • Step %d: %s %s", idx+1, step.get('tool'), step.get('tool_args'))

            workflow_state = ""
            if plan:
                logger.info("🤖 [Execution Engine] Running deterministic %d-step pipeline...", len(plan))
            
            tools_used = []
            all_sources = []

            # Async tool run helper
            async def run_tool_async(step_to_run):
                t_name = step_to_run.get("tool")
                t_args = step_to_run.get("tool_args", {})
                s_num = step_to_run.get("step", 1)
                
                if t_name not in tool_dict:
                    logger.warning("❌ [TOOL NOT FOUND] Step %d: '%s' not registered", s_num, t_name)
                    return {"tool": t_name, "result": f"Tool '{t_name}' not found.", "success": False, "step": s_num, "ux_text": f"Using {t_name}"}
                
                step_tool = tool_dict[t_name]
                t_ui = TOOL_UX_MAP.get(t_name, {"emoji": "⚙️", "text": f"Using {t_name}"})
                ux_text = t_ui["text"]
                
                logger.info("⚙️ [TOOL] Step %d: %s %s", s_num, t_name, t_args)
                start_t = time.time()
                try:
                    res = await step_tool.ainvoke(t_args)
                    elapsed = time.time() - start_t
                    logger.info("✅ [TOOL] Step %d: %s done in %.2fs", s_num, t_name, elapsed)
                    return {"tool": t_name, "result": res, "success": True, "step": s_num, "ux_text": ux_text}
                except Exception as ex:
                    elapsed = time.time() - start_t
                    logger.error("❌ [TOOL] Step %d: %s failed in %.2fs | %s", s_num, t_name, elapsed, ex)
                    return {"tool": t_name, "result": f"Execution failed: {ex}", "success": False, "step": s_num, "ux_text": ux_text}

            MAX_AGENT_LOOPS = 2
            current_plan = plan

            for loop_idx in range(MAX_AGENT_LOOPS):
                # 1. Filter out step tools that exist
                valid_steps = [s for s in current_plan if s.get("tool") in tool_dict]
                if not valid_steps:
                    break
                
                # 3. Execute requested tools in parallel concurrently
                t_names = [s.get("tool") for s in valid_steps]
                ux_texts = [TOOL_UX_MAP.get(t, {"emoji": "⚙️", "text": "Running tool"})["text"] for t in t_names]
                yield {"status": f"{', '.join(ux_texts)}..."}
                results = await asyncio.gather(*[run_tool_async(step) for step in valid_steps])
                
                for res in results:
                    # Accumulate tool outputs into workflow log context
                    tool_result_str = str(res["result"])
                    logger.debug("[TOOL OUTPUT] %s: %s", res['tool'], tool_result_str[:200])
                    if len(tool_result_str) > 15000:
                        tool_result_str = tool_result_str[:15000] + "\n...[TRUNCATED TO SAVE MEMORY]"
                    
                    status_label = "RESULT" if res.get("success", False) else "FAILED"
                    workflow_state += f"--- STEP {res['step']} ({res['tool']}) {status_label} ---\n{tool_result_str}\n\n"
                    
                    # Track web URL links or document tags for final references card
                    if res["tool"] == "document_search_tool" and "Uploaded Document" not in all_sources:
                        all_sources.append("Uploaded Document")
                    urls = re.findall(r'(?:Source URL|Link|Direct Link):\s*(https?://[^\s\n<]+)', str(res["result"]))
                    for u in urls:
                        if u not in all_sources: all_sources.append(u)

                # Critic Loop evaluation or bypass check
                if loop_idx < MAX_AGENT_LOOPS - 1:
                    # OPTIMIZATION: If all execution plan tool calls are fully successful and contain non-empty data, bypass the critic!
                    all_successful = all(res.get("success", False) for res in results)
                    has_data = any(res.get("success", False) and len(str(res.get("result", ""))) > 50 for res in results)
                    
                    if all_successful and has_data:
                        logger.info("✅ [Critic Agent] Tool results are successful and contain data. Bypassing critic review.")
                        break
                    logger.info("🧐 [Critic Agent] Evaluating if we have enough data...")
                    
                    critic_sys = get_critic_system_prompt(tool_descriptions)
                    critic_msgs = [SystemMessage(content=critic_sys), langchain_messages[-1], HumanMessage(content=f"PIPELINE EXECUTION DATA:\n{workflow_state}")]
                    
                    try:
                        critic_resp = await _get_llm().ainvoke(critic_msgs)
                        critic_text = critic_resp.content.strip()
                        
                        if critic_text.upper().startswith("YES") or "YES" in critic_text[:10].upper():
                            logger.info("✅ [Critic Agent] Data is sufficient. Proceeding to synthesis.")
                            break
                        else:
                            match = re.search(r'```(?:json)?\s*(.*?)\s*```', critic_text, re.DOTALL | re.IGNORECASE)
                            clean_json = match.group(1) if match else critic_text[critic_text.find('{'):critic_text.rfind('}')+1]
                            new_plan_decision = json.loads(clean_json, strict=False)
                            
                            if isinstance(new_plan_decision, dict) and "plan" in new_plan_decision and new_plan_decision["plan"]:
                                current_plan = new_plan_decision["plan"]
                                logger.info("🔄 [Critic Agent] Data incomplete! Triggering loop %d with %d new steps...", loop_idx+2, len(current_plan))
                                workflow_state += "\n--- CRITIC FEEDBACK: Gathering more data ---\n"
                                continue
                            
                            break
                    except Exception as e:
                        logger.warning("⚠️ [Critic Agent] Failed to evaluate or parse: %s", e)
                        break
                
            # Synthesizer Prompt assembly
            yield {"status": "Analyzing results & compiling report..."}
            synth_base_prompt = build_synth_prompt(langchain_messages[0].content)
                
            synth_sys_content = (
                "🚨 CRITICAL MODE: YOU ARE IN FINAL RESPONSE SYNTHESIS MODE.\n"
                "ALL REQUIRED TOOLS HAVE ALREADY BEEN EXECUTED BY THE SYSTEM. THEIR OUTPUT DATA IS PROVIDED IN THE 'PIPELINE EXECUTION DATA' SECTION BELOW.\n"
                "DO NOT OUTPUT ANY JSON, DO NOT OUTPUT TOOL CALLS, DO NOT OUTPUT FUNCTION PAYLOADS LIKE `{\"name\": ...}`.\n"
                "YOU MUST RESPOND DIRECTLY TO THE USER IN CLEAN CONVERSATIONAL MARKDOWN USING THE RETRIEVED DATA.\n\n"
                + synth_base_prompt
                + f"\n\n--- PIPELINE EXECUTION DATA ---\n{workflow_state}\n\nFINAL INSTRUCTION:\n"
                "1. SILENT RETRIEVAL INTEGRATION: All requested tools (including MCP workspace filesystem, document vault, email intelligence, or web tools) have ALREADY been executed and their output data is provided in PIPELINE EXECUTION DATA above.\n"
                "2. DIRECT RESPONSE FORMAT: Provide the final answer, solution, code changes, or summary directly to the user. Do NOT describe your operational steps, pre-announcements, or say things like 'I will read', 'I inspected the folder', 'I will open file X'. Never output internal role names ('Chitti', 'Reddy') or internal monologues ('The user wants me to...'). Deliver the complete, actionable answer directly.\n"
                "3. ACCURACY & EVIDENCE: Use the retrieved data accurately. If analyzing code, files, or architecture, behave like a Senior Lead AI Architect (Antigravity-level). Provide exact code blocks/diffs, explain architectural patterns, and format file references as clickable Markdown links (e.g. `[filename.py](file:///path/to/file)`).\n"
                "4. NO RAW ARTIFACTS OR JSON LEAKS: Never output raw python print tool calls, raw JSON tool arrays `[{\"name\": ...}]`, raw JSON tool payloads, raw JSON execution plans, developer logs, or internal reasoning XML tags (<thinking>, <antThinking>, <tool_code>). Output ONLY clean Markdown for the user.\n"
                "5. FOLLOW-UP OPTIONS: Wrap exactly 3 to 4 follow-up options inside <followup> and </followup> tags at the very end of your response, with each option on a new line starting with a hyphen. Stop immediately after the closing tag.\n"
                "6. SENIOR-LEVEL ENGINEERING REASONING: Infer core engineering concepts and explain how details map to microservices, concurrency, distributed queues, and fault tolerance. Reason like a Senior Architect rather than a simple document summarizer.\n"
                "7. FACTUAL GROUNDING: Differentiate clearly between established facts, reasonable inferences, suggestions, and illustrative hypothetical examples. Do not blur these categories, and never present assumptions or estimates as verified facts.\n"
            )
            
            synth_messages = [SystemMessage(content=synth_sys_content)] + langchain_messages[1:]
            
            # 🔍 Print final prompt to terminal safely for debugging (encoding as ascii to prevent Windows CP1252 crash)
            logger.info("🚀 [LLM] Synthesizing answer from %d tool result(s)", len(workflow_state.split('--- STEP')))
            
            first_token_yielded = False
            cleaner = StreamingCleaner()
            
            async for chunk in _get_llm().astream(synth_messages):
                if chunk.content:
                    if not first_token_yielded:
                        first_token_yielded = True
                        if all_sources:
                            sources_json = json.dumps(all_sources)
                            sources_b64 = base64.b64encode(sources_json.encode('utf-8')).decode('utf-8')
                            yield f"<div class='hidden-sources' style='display:none;' data-sources='{sources_b64}'></div>"
                    yielded_any = True
                    
                    cleaned_chunk = cleaner.process_chunk(chunk.content)
                    if cleaned_chunk:
                        yield cleaned_chunk
                    
            if not first_token_yielded:
                if workflow_state:
                    yield workflow_state[:1500] + "\n\n*(Note: Displaying raw tool output due to synthesis fallback)*"
                    yielded_any = True
                if all_sources:
                    sources_json = json.dumps(all_sources)
                    sources_b64 = base64.b64encode(sources_json.encode('utf-8')).decode('utf-8')
                    yield f"<div class='hidden-sources' style='display:none;' data-sources='{sources_b64}'></div>"
                    
            if yielded_any:
                logger.info("✅ Response streamed successfully")

        if not yielded_any:
            yield "I am sorry, but I was unable to generate a response."
            
        # Trigger background Memory summaries tag/compression
        compress_and_save_memories_bg(conversation_history, user_id, session_id, _get_llm())
            
    except Exception as e:
        err_str = str(e).lower()
        if "maximum input length" in err_str or "context length" in err_str or "input_tokens" in err_str or "context_length" in err_str or "too many tokens" in err_str:
            yield "I apologize, but the data retrieved for that request (or the chat history) was too large for me to process all at once. Could you please narrow down your question or specify exactly what details you need?"
        elif "system message must be at the beginning" in err_str:
            yield "I encountered an API configuration error: System message must be at the beginning of the messages list. Please report this to the developer."
        elif "400" in err_str or "bad request" in err_str:
            yield f"I encountered an invalid request formatting error (HTTP 400 Bad Request) from the AI server. Details: {e}"
        elif "502" in err_str or "bad gateway" in err_str or "peer closed connection" in err_str or "timeout" in err_str:
            yield "The AI server is currently overloaded or temporarily unreachable (Connection Error). Please wait a few moments and try asking again!"
        else:
            yield f"I'm sorry, but I encountered an unexpected error while processing your request: {e}"
        logger.error("❌ [Agent Execution Error] %s", e, exc_info=True)

async def generate_chat_title(user_message: str) -> str:
    """Generates a short, professional title (max 4 words) based on the first user message."""
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant that generates extremely concise, professional titles for chat sessions. "
                       "Read the user's first message and generate a title of 1 to 4 words. "
                       "Do not use quotes, punctuation, or conversational filler. Example: 'Python Script Debugging', 'Greetings', 'Resume Analysis'."),
            ("user", "{message}")
        ])
        chain = prompt | _get_llm() | StrOutputParser()
        title = await chain.ainvoke({"message": user_message})
        return title.strip().strip('"').strip("'")
    except Exception as e:
        logger.warning("⚠️ [Title Gen] Failed: %s", e)
        return user_message[:25] + "..."
