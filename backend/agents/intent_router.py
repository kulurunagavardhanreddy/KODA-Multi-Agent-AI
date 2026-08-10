# intent_router.py

import re
import json
import logging

logger = logging.getLogger(__name__)

def is_tool_execution_plan(content_buffer: str) -> bool:
    """Evaluates if the buffered LLM output represents a tool execution plan or tool call payload."""
    stripped = content_buffer.lstrip()
    if not stripped:
        return False
        
    # Standard JSON start tokens or code blocks
    if stripped.startswith("{") or stripped.startswith("[") or stripped.startswith("```"):
        return True
        
    lower_strip = stripped.lower()
    if ("{" in stripped or "[" in stripped or "```" in stripped) and any(
        k in lower_strip for k in ['"plan"', '"tool"', '"tool_name"', '"tool_calls"', '"arguments"', '"tool_args"', '"path"', '"paths"', '"query"', 'mcp_']
    ):
        return True
        
    # Check for python-like tool calls (e.g. print(mcp_...) or mcp_...)
    if re.search(r'(?:print\s*\(\s*)?[a-zA-Z0-9_]+_tool[a-zA-Z0-9_]*\s*\(', stripped) or \
       re.search(r'(?:print\s*\(\s*)?mcp_[a-zA-Z0-9_]*\s*\(', stripped):
        return True
        
    return False

def parse_execution_plan(plan_buffer: str) -> list:
    """Safely extracts and parses tool execution plan JSON list or Python-like function calls from LLM output."""
    res_clean = plan_buffer.strip()
    
    # 1. First, check if it's a JSON plan
    plan = []
    if "{" in res_clean or "[" in res_clean:
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', res_clean, re.DOTALL | re.IGNORECASE)
        if match:
            res_clean = match.group(1)
        else:
            start = res_clean.find('{')
            end = res_clean.rfind('}')
            if start != -1 and end != -1:
                res_clean = res_clean[start:end+1]
        try:
            plan_decision = json.loads(res_clean.strip(), strict=False)
            if isinstance(plan_decision, dict):
                plan = plan_decision.get("plan") or plan_decision.get("tool_calls")
                if plan is None:
                    if "tool" in plan_decision or "tool_name" in plan_decision:
                        plan = [plan_decision]
                    else:
                        plan = []
            elif isinstance(plan_decision, list):
                plan = plan_decision
            
            # Normalize steps format dynamically (handling tool_name/arguments variations)
            if plan and isinstance(plan, list):
                normalized = []
                for idx, s in enumerate(plan):
                    if isinstance(s, dict):
                        t_name = s.get("tool") or s.get("tool_name")
                        t_args = s.get("tool_args") or s.get("arguments") or {}
                        s_num = s.get("step") or (idx + 1)
                        if t_name:
                            normalized.append({
                                "step": s_num,
                                "tool": t_name,
                                "tool_args": t_args
                            })
                if normalized:
                    return normalized
        except Exception:
            pass

    # 2. Fallback: Parse Python-like tool calls (e.g., print(mcp_filesystem_list_directory(path="...")))
    # Matches optional 'print(' followed by a tool name, then '(' and parameters, ending with optional ')'
    py_calls = re.findall(r'(?:print\s*\(\s*)?([a-zA-Z0-9_]+)\s*\((.*?)\)(?:\s*\))?', res_clean)
    if py_calls:
        plan = []
        for tool_name, args_str in py_calls:
            if tool_name in ["print", "str", "int", "list", "dict", "len"]:
                continue
            # Parse arguments like: path="C:/Users/nagav/Downloads/Naga_MyHub/chatbot_agents"
            tool_args = {}
            arg_matches = re.findall(r'([a-zA-Z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,)]+))', args_str)
            for arg_name, d_val, s_val, u_val in arg_matches:
                val = d_val or s_val or u_val
                tool_args[arg_name] = val
            plan.append({
                "step": len(plan) + 1,
                "tool": tool_name,
                "tool_args": tool_args
            })
        if plan:
            logger.info("🧭 [Router] Successfully parsed Python-like tool calls: %s", plan)
            return plan

    # 3. Final AST fallback for dict representations
    try:
        import ast
        clean_for_ast = res_clean.strip().replace("null", "None").replace("true", "True").replace("false", "False")
        plan_decision = ast.literal_eval(clean_for_ast)
        if isinstance(plan_decision, dict):
            plan = plan_decision.get("plan") or plan_decision.get("tool_calls")
            if plan is None:
                if "tool" in plan_decision or "tool_name" in plan_decision:
                    plan = [plan_decision]
                else:
                    plan = []
        elif isinstance(plan_decision, list):
            plan = plan_decision
            
        # Normalize steps format for AST fallback
        if plan and isinstance(plan, list):
            normalized = []
            for idx, s in enumerate(plan):
                if isinstance(s, dict):
                    t_name = s.get("tool") or s.get("tool_name")
                    t_args = s.get("tool_args") or s.get("arguments") or {}
                    s_num = s.get("step") or (idx + 1)
                    if t_name:
                        normalized.append({
                            "step": s_num,
                            "tool": t_name,
                            "tool_args": t_args
                        })
            if normalized:
                return normalized
    except Exception as e2:
        logger.warning("⚠️ [Router] Failed to parse JSON plan: %s", e2)
        
    return []
