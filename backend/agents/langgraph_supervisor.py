# backend/agents/langgraph_supervisor.py
"""
LangGraph Multi-Agent Supervisor Architecture
----------------------------------------------
Implements pure LangGraph `StateGraph` workflows with explicit state management,
node definitions, conditional routing edges, tool execution concurrency, and 
Critic reflection loops.
"""

import os
import re
import json
import time
import base64
import asyncio
import logging
import requests
from typing import TypedDict, Annotated, List, Dict, Any, Optional

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

try:
    from backend.config import GEMINI_API_KEY
    from backend.providers import get_provider
    from backend.prompts.system_prompts import get_koda_system_prompt
    from backend.prompts.agent_prompts import get_critic_system_prompt
    from backend.memory.conversation_memory import build_history_context, compress_and_save_memories_bg
    from backend.agents.intent_router import is_tool_execution_plan, parse_execution_plan
    from backend.agents.supervisor import classify_query_intent, build_synth_prompt, clean_llm_output, StreamingCleaner, _get_llm
except ImportError:
    from ..config import GEMINI_API_KEY
    from ..providers import get_provider
    from ..prompts.system_prompts import get_koda_system_prompt
    from ..prompts.agent_prompts import get_critic_system_prompt
    from ..memory.conversation_memory import build_history_context, compress_and_save_memories_bg
    from .intent_router import is_tool_execution_plan, parse_execution_plan
    from .supervisor import classify_query_intent, build_synth_prompt, clean_llm_output, StreamingCleaner, _get_llm

logger = logging.getLogger(__name__)

# ==========================================
# 1. DEFINE LANGGRAPH STATE SCHEMAS
# ==========================================

class SupervisorState(TypedDict):
    """Core state schema passed between LangGraph nodes."""
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: str
    session_id: str
    user_location: str
    image_b64: str
    intent: str
    current_plan: List[Dict[str, Any]]
    workflow_state: str
    all_sources: List[str]
    next_node: str
    loop_count: int
    final_output: str

# ==========================================
# 2. DEFINE LANGGRAPH NODE FUNCTIONS
# ==========================================

async def intent_router_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 1: Evaluates user query intent using structural rules & vector matching."""
    logger.info("📡 [LangGraph Node: IntentRouter] Evaluating request state...")
    messages = state.get("messages", [])
    user_latest_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_latest_query = msg.content if isinstance(msg.content, str) else str(msg.content[0].get("text", ""))
            break
            
    intent = classify_query_intent(user_latest_query) if user_latest_query else "GENERAL"
    
    if intent in ["GREETING", "CONVERSATION"]:
        logger.info("🎯 [LangGraph Router] Casual conversation fast-path -> Synthesis")
        return {"intent": intent, "next_node": "synthesis"}
        
    # Check vector store for document match
    user_id = state.get("user_id", "")
    if user_id and user_latest_query:
        try:
            from backend.loaders.document_loader import get_vector_store
            from qdrant_client.http import models
            vector_store = get_vector_store()
            qdrant_filter = models.Filter(
                must=[models.FieldCondition(key="metadata.owner", match=models.MatchValue(value=user_id))]
            )
            docs_with_scores = vector_store.similarity_search_with_score(user_latest_query, k=3, filter=qdrant_filter)
            if any(score >= 0.55 for _, score in docs_with_scores):
                logger.info("🎯 [LangGraph Router] Fast RAG vector match -> RAG Node")
                return {"intent": "DOCUMENT_MATCH", "next_node": "rag_retrieval"}
        except Exception as e:
            logger.warning("⚠️ [LangGraph Router] Vector check failed: %s", e)
            
    logger.info("🎯 [LangGraph Router] Tool query -> Planner Node")
    return {"intent": intent, "next_node": "planner"}


async def rag_retrieval_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 2: Executes RAG vector retrieval workflow from Qdrant vault."""
    logger.info("📄 [LangGraph Node: RAGRetrieval] Retrieving document context...")
    user_latest_query = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            user_latest_query = msg.content if isinstance(msg.content, str) else str(msg.content[0].get("text", ""))
            break
            
    from backend.workflows.rag_workflow import run_rag_search
    rag_context = run_rag_search(user_latest_query, state.get("user_id", ""))
    
    formatted_state = f"--- STEP 1 (document_search_tool) RESULT ---\n{rag_context}\n\n"
    return {
        "workflow_state": formatted_state,
        "all_sources": ["Uploaded Document"],
        "next_node": "synthesis"
    }


async def planner_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 3: Generates structured multi-tool JSON execution plan."""
    logger.info("🧠 [LangGraph Node: Planner] Formulating tool plan...")
    user_id = state.get("user_id", "")
    from backend.tools import get_agent_tools
    tools = get_agent_tools(user_id)
    tool_descriptions = "\n".join([f"- {t.name}: {t.description}" for t in tools])
    
    current_system_time = time.strftime("%A, %B %d, %Y | Current Time: %I:%M %p")
    provider_id = _get_llm().__class__.__name__
    sys_prompt = get_koda_system_prompt(current_system_time, "", "", "", tool_descriptions, provider_id)
    
    langchain_messages = [SystemMessage(content=sys_prompt)] + state.get("messages", [])
    
    response = await _get_llm().ainvoke(langchain_messages)
    raw_text = response.content if isinstance(response.content, str) else str(response.content)
    
    plan = parse_execution_plan(raw_text)
    if not plan and is_tool_execution_plan(raw_text):
        fallback_query = langchain_messages[-1].content
        plan = [{"step": 1, "tool": tools[0].name, "tool_args": {"query": str(fallback_query)[:100]}}] if tools else []
        
    logger.info("🎯 [LangGraph Planner] Generated %d-step tool plan", len(plan))
    return {
        "current_plan": plan,
        "next_node": "tool_execution" if plan else "synthesis"
    }


async def tool_execution_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 4: Concurrently executes sub-agent tools (Doc, Web, Code, Travel, MCP)."""
    logger.info("⚙️ [LangGraph Node: ToolExecution] Executing sub-agent tools...")
    user_id = state.get("user_id", "")
    from backend.tools import get_agent_tools
    tools = get_agent_tools(user_id)
    tool_dict = {t.name: t for t in tools}
    
    plan = state.get("current_plan", [])
    valid_steps = [s for s in plan if s.get("tool") in tool_dict]
    
    async def _run_single_tool(step):
        t_name = step.get("tool")
        t_args = step.get("tool_args", {})
        tool_obj = tool_dict[t_name]
        try:
            res = await tool_obj.ainvoke(t_args)
            return {"tool": t_name, "result": res, "success": True, "step": step.get("step", 1)}
        except Exception as ex:
            return {"tool": t_name, "result": f"Execution failed: {ex}", "success": False, "step": step.get("step", 1)}
            
    results = await asyncio.gather(*[_run_single_tool(s) for s in valid_steps]) if valid_steps else []
    
    workflow_state = state.get("workflow_state", "")
    sources = list(state.get("all_sources", []))
    
    for res in results:
        status_label = "RESULT" if res.get("success") else "FAILED"
        workflow_state += f"--- STEP {res['step']} ({res['tool']}) {status_label} ---\n{res['result']}\n\n"
        if res["tool"] == "document_search_tool" and "Uploaded Document" not in sources:
            sources.append("Uploaded Document")
        urls = re.findall(r'(?:Source URL|Link|Direct Link):\s*(https?://[^\s\n<]+)', str(res["result"]))
        for u in urls:
            if u not in sources: sources.append(u)
            
    return {
        "workflow_state": workflow_state,
        "all_sources": sources,
        "next_node": "critic_reflection"
    }


async def critic_reflection_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 5: Reflection node evaluating data completeness and triggering re-plan loops."""
    logger.info("🧐 [LangGraph Node: CriticReflection] Reviewing data sufficiency...")
    loop_count = state.get("loop_count", 0) + 1
    if loop_count >= 2 or not state.get("current_plan"):
        logger.info("✅ [LangGraph Critic] Data approved or loop limit reached -> Synthesis")
        return {"loop_count": loop_count, "next_node": "synthesis"}
        
    workflow_state = state.get("workflow_state", "")
    from backend.tools import get_agent_tools
    tools = get_agent_tools(state.get("user_id", ""))
    tool_descriptions = "\n".join([f"- {t.name}: {t.description}" for t in tools])
    
    critic_sys = get_critic_system_prompt(tool_descriptions)
    critic_msgs = [
        SystemMessage(content=critic_sys),
        state["messages"][-1],
        HumanMessage(content=f"PIPELINE EXECUTION DATA:\n{workflow_state}")
    ]
    
    try:
        response = await _get_llm().ainvoke(critic_msgs)
        critic_text = response.content.strip() if isinstance(response.content, str) else str(response.content)
        
        if critic_text.upper().startswith("YES") or "YES" in critic_text[:10].upper():
            logger.info("✅ [LangGraph Critic] Reflection approved -> Synthesis")
            return {"loop_count": loop_count, "next_node": "synthesis"}
        else:
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', critic_text, re.DOTALL | re.IGNORECASE)
            clean_json = match.group(1) if match else critic_text[critic_text.find('{'):critic_text.rfind('}')+1]
            new_plan_decision = json.loads(clean_json, strict=False)
            new_plan = new_plan_decision.get("plan", [])
            if new_plan:
                logger.info("🔄 [LangGraph Critic] Data incomplete! Loop %d with %d steps", loop_count + 1, len(new_plan))
                return {"current_plan": new_plan, "loop_count": loop_count, "next_node": "tool_execution"}
    except Exception as e:
        logger.warning("⚠️ [LangGraph Critic] Evaluation error: %s", e)
        
    return {"loop_count": loop_count, "next_node": "synthesis"}


async def synthesis_node(state: SupervisorState) -> Dict[str, Any]:
    """Node 6: Synthesizes final response to user."""
    logger.info("🚀 [LangGraph Node: Synthesis] Generating response...")
    current_system_time = time.strftime("%A, %B %d, %Y | Current Time: %I:%M %p")
    provider_id = _get_llm().__class__.__name__
    sys_prompt = get_koda_system_prompt(current_system_time, "", "", "", "", provider_id)
    
    workflow_state = state.get("workflow_state", "")
    if workflow_state:
        synth_prompt = (
            "🚨 FINAL SYNTHESIS MODE: ALL TOOLS EXECUTED.\n"
            + build_synth_prompt(sys_prompt)
            + f"\n\n--- PIPELINE EXECUTION DATA ---\n{workflow_state}\n"
            + "\nRespond directly to the user in clean conversational Markdown."
        )
    else:
        synth_prompt = sys_prompt
        
    messages = [SystemMessage(content=synth_prompt)] + state.get("messages", [])
    response = await _get_llm().ainvoke(messages)
    final_output = response.content if isinstance(response.content, str) else str(response.content)
    
    return {"final_output": final_output, "next_node": END}


# ==========================================
# 3. BUILD & COMPILE LANGGRAPH WORKFLOW
# ==========================================

def create_supervisor_graph():
    """Constructs and compiles the official LangGraph Multi-Agent Supervisor StateGraph."""
    workflow = StateGraph(SupervisorState)

    # Add Nodes
    workflow.add_node("intent_router", intent_router_node)
    workflow.add_node("rag_retrieval", rag_retrieval_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("tool_execution", tool_execution_node)
    workflow.add_node("critic_reflection", critic_reflection_node)
    workflow.add_node("synthesis", synthesis_node)

    # Add Edges & Conditional Routing
    workflow.add_edge(START, "intent_router")
    
    workflow.add_conditional_edges(
        "intent_router",
        lambda state: state["next_node"],
        {
            "rag_retrieval": "rag_retrieval",
            "planner": "planner",
            "synthesis": "synthesis"
        }
    )
    
    workflow.add_edge("rag_retrieval", "synthesis")
    workflow.add_edge("planner", "tool_execution")
    workflow.add_edge("tool_execution", "critic_reflection")
    
    workflow.add_conditional_edges(
        "critic_reflection",
        lambda state: state["next_node"],
        {
            "tool_execution": "tool_execution",
            "synthesis": "synthesis"
        }
    )
    
    workflow.add_edge("synthesis", END)

    # Compile Graph
    compiled_graph = workflow.compile()
    logger.info("✨ [LangGraph Engine] Successfully compiled Multi-Agent Supervisor StateGraph!")
    return compiled_graph

# Compile Graph
langgraph_agent = create_supervisor_graph()

async def chat_with_langgraph(conversation_history: list, user_location: str = "", user_id: str = "", image_b64: str = "", session_id: str = ""):
    """Streams responses from the compiled LangGraph StateGraph engine token-by-token."""
    initial_state = {
        "messages": conversation_history,
        "user_id": user_id,
        "session_id": session_id,
        "user_location": user_location,
        "image_b64": image_b64,
        "intent": "GENERAL",
        "current_plan": [],
        "workflow_state": "",
        "all_sources": [],
        "next_node": "intent_router",
        "loop_count": 0,
        "final_output": ""
    }
    
    yield {"status": "Initializing LangGraph StateGraph engine..."}
    
    async for event in langgraph_agent.astream(initial_state, stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "intent_router":
                next_target = node_output.get("next_node", "planner")
                yield {"status": f"LangGraph Router: Selected node '{next_target}'"}
            elif node_name == "rag_retrieval":
                yield {"status": "LangGraph RAG: Retrieving vector document context..."}
            elif node_name == "planner":
                yield {"status": "LangGraph Planner: Formulating tool execution plan..."}
            elif node_name == "tool_execution":
                yield {"status": "LangGraph Tools: Running multi-agent tool execution..."}
            elif node_name == "critic_reflection":
                yield {"status": "LangGraph Critic: Evaluated data completeness"}
            elif node_name == "synthesis":
                final_text = node_output.get("final_output", "")
                if final_text:
                    yield final_text

