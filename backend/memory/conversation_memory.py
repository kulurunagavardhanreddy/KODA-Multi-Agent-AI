# conversation_memory.py

import logging
import re
import asyncio
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.prompts.agent_prompts import get_memory_summarization_prompt

logger = logging.getLogger(__name__)

MAX_HISTORY_CHARS = 6000

def strip_html_tags(text: str) -> str:
    """Strips all HTML tags and their contents for prompt history building."""
    # 1. Remove followup tags and their contents completely
    text = re.sub(r"<followup>.*?</followup>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<followup>.*?\n*", "", text, flags=re.DOTALL) # Catch unclosed tag at end of stream if any
    
    # 2. Strip blocks by their class containers (including all inner contents)
    text = re.sub(r"<div class='koda-thinking-block'>.*?</div>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<div class=\"koda-thinking-block\">.*?</div>\n*", "", text, flags=re.DOTALL)
    
    text = re.sub(r"<div class='agent-execution-block'>.*?</div>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<div class=\"agent-execution-block\">.*?</div>\n*", "", text, flags=re.DOTALL)
    
    text = re.sub(r"<div class='agent-step'>.*?</div>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<div class=\"agent-step\">.*?</div>\n*", "", text, flags=re.DOTALL)
    
    text = re.sub(r"<div class='koda-response-started'.*?></div>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<div class=\"koda-response-started\".*?></div>\n*", "", text, flags=re.DOTALL)
    
    text = re.sub(r"<div class='hidden-sources'>.*?</div>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<div class=\"hidden-sources\">.*?</div>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<div class='hidden-sources'.*?>.*?</div>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<div class=\"hidden-sources\".*?>.*?</div>\n*", "", text, flags=re.DOTALL)

    # 3. Strip nested span agent pills and their text
    text = re.sub(r"<span class='agent-pill.*?</span>\n*", "", text, flags=re.DOTALL)
    text = re.sub(r"<span class=\"agent-pill.*?</span>\n*", "", text, flags=re.DOTALL)

    # 4. Clean up any literal text chunks left behind from stripped elements
    text = text.replace("✓Thinking Process", "")
    text = text.replace("✗Thinking Process", "")
    text = text.replace("Thinking...✓Thinking Process", "")
    text = text.replace("Thinking...✓Searching web", "")
    text = text.replace("Thinking...✓Searching documents", "")
    text = text.replace("Thinking...✓Thinking ProcessThinking...", "")
    
    # Clean up multiple occurrences of "Thinking..." at the beginning
    text = re.sub(r"^(?:\s*Thinking\.\.\.\s*)+", "", text)

    # 5. Strip any generic HTML tags (leaving clean text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()

def build_history_context(conversation_history: list, image_b64: str = "") -> list:
    """Applies a sliding window characters budget to anchor context and inject vision assets."""
    safe_history = []
    current_chars = 0
    
    # 1. Anchor the first message
    if conversation_history:
        first_msg = conversation_history[0]
        content = first_msg.content if isinstance(first_msg.content, str) else str(first_msg.content)
        if isinstance(first_msg, AIMessage):
            content = strip_html_tags(content)
        if len(content) > 3000:
            content = content[:3000] + "..."
        safe_history.append(HumanMessage(content=content) if isinstance(first_msg, HumanMessage) else AIMessage(content=content))
        current_chars += len(content)

    # 2. Fill budget working backwards from the newest messages
    recent_buffer = []
    for msg in reversed(conversation_history[1:]):
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if isinstance(msg, AIMessage):
            content = strip_html_tags(content)
        msg_len = len(content)
        
        if current_chars + msg_len > MAX_HISTORY_CHARS:
            if len(recent_buffer) == 0:
                allowed = MAX_HISTORY_CHARS - current_chars
                if allowed > 500:
                    truncated = content[:allowed] + "\n...[Truncated]"
                    recent_buffer.append(HumanMessage(content=truncated) if isinstance(msg, HumanMessage) else AIMessage(content=truncated))
            break
            
        current_chars += msg_len
        if isinstance(msg, HumanMessage):
            recent_buffer.append(HumanMessage(content=content))
        elif isinstance(msg, AIMessage):
            recent_buffer.append(AIMessage(content=content))
        else:
            recent_buffer.append(msg)

    safe_history.extend(reversed(recent_buffer))
    
    # 3. Inject image if base64 vision asset is attached
    if image_b64 and len(safe_history) > 0 and isinstance(safe_history[-1], HumanMessage):
        last_msg = safe_history.pop()
        multimodal_content = [
            {"type": "text", "text": last_msg.content},
            {"type": "image_url", "image_url": {"url": image_b64}}
        ]
        safe_history.append(HumanMessage(content=multimodal_content))
        
    return safe_history

def compress_and_save_memories_bg(conversation_history: list, user_id: str, session_id: str, llm):
    """Background task orchestrator to trigger memory compression."""
    logger.info("🧠 [Memory Manager] Checking session '%s'. Total messages: %d", session_id, len(conversation_history))
    if session_id and len(conversation_history) > 8:
        if (len(conversation_history) + 1) % 4 == 0:
            async def run_memory_compression():
                try:
                    from backend.database.chat_database import save_conversation_memory, get_session_memories_dict
                    docs_to_summarize = conversation_history[-5:-1]
                    if docs_to_summarize:
                        text_to_summarize = "\n".join([f"{'User' if isinstance(m, HumanMessage) else 'AI'}: {m.content}" for m in docs_to_summarize])
                        clean_text = text_to_summarize.lower().strip()
                        is_filler = len(clean_text) < 150 or all(w in ["hi", "hello", "thanks", "thank you", "welcome", "ok", "hey", "bye", "good", "great", "cool", "yes", "no", "sure", "please", "buddy", "chanti", "koda", "diagram", "show", "give", "code"] for w in re.findall(r'\b\w+\b', clean_text))
                        
                        if len(text_to_summarize) > 150 and not is_filler:
                            logger.info("🧠 [Memory Manager] Triggering Topic Tagging & Compression in background!")
                            existing_dict = get_session_memories_dict(user_id, session_id)
                            dict_str = "\n".join([f"- [{k}]: {v}" for k, v in existing_dict.items()]) if existing_dict else "No existing memories."
                            
                            sum_prompt = ChatPromptTemplate.from_messages([
                                ("system", get_memory_summarization_prompt()),
                                ("user", "{text}")
                            ])
                            sum_chain = sum_prompt | llm | StrOutputParser()
                            new_memory_raw = await sum_chain.ainvoke({"existing_dict": dict_str, "text": text_to_summarize})
                            new_memory_raw = new_memory_raw.strip()
                            
                            if new_memory_raw != "SKIP":
                                import json
                                json_str = new_memory_raw
                                json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", new_memory_raw, re.IGNORECASE)
                                if json_match:
                                    json_str = json_match.group(1)
                                try:
                                    mem_data = json.loads(json_str)
                                    category = mem_data.get("category", "General").replace("[", "").replace("]", "").replace("*", "").strip()
                                    summary = mem_data.get("summary", "").strip()
                                    memory_type = mem_data.get("memory_type", "general").strip()
                                    entities = mem_data.get("entities", [])
                                    importance = int(mem_data.get("importance", 5))
                                    
                                    if summary:
                                        save_conversation_memory(
                                            user_id=user_id, 
                                            session_id=session_id, 
                                            category=category, 
                                            summary_text=summary,
                                            memory_type=memory_type,
                                            entities=entities,
                                            importance=importance
                                        )
                                        logger.info("🧠 [Memory Manager] ✅ Saved '%s' topic memory to long-term vault!", category)
                                except Exception as json_err:
                                    logger.warning("⚠️ [Memory Manager] Failed to parse summary JSON: %s. Raw: %s", json_err, new_memory_raw)
                        else:
                            logger.info("🧠 [Memory Manager] Skipping: Messages are conversational filler or too short.")
                except Exception as sum_err:
                    logger.error("⚠️ [Memory Manager] Failed: %s", sum_err)
            
            asyncio.create_task(run_memory_compression())
        else:
            logger.info("🧠 [Memory Manager] Skipping: Rolling memory updates every 4 messages. (Current: %d)", len(conversation_history))
    else:
        if not session_id:
            logger.info("🧠 [Memory Manager] Skipping: No active session ID.")
        else:
            logger.info("🧠 [Memory Manager] Skipping: Chat is too short (Needs > 8 messages).")
