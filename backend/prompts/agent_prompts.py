# agent_prompts.py

def get_critic_system_prompt(tool_descriptions: str) -> str:
    """Generates system prompt for the Critic agent evaluating gathered pipeline execution data."""
    return f"""You are the CRITIC AGENT in a Multi-Agent AI system.
Your job is to evaluate if the PIPELINE EXECUTION DATA has fully answered the user's latest message.
If the data is SUFFICIENT or if tools failed and you cannot do anything else, reply EXACTLY with the word "YES".
If the data is INCOMPLETE, reply with a new raw JSON execution plan to search for the missing data.
AVAILABLE TOOLS:
{tool_descriptions}
JSON FORMAT:
{{"plan": [{{"step": 1, "tool": "web_search_tool", "tool_args": {{"query": "..."}}}}]}}"""

def get_memory_summarization_prompt() -> str:
    """System prompt for categorization and generation of granular memory summaries."""
    return """You are an AI memory manager that categorizes conversations to build a Granular Topic Memory.

CURRENT MEMORIES:
{existing_dict}

INSTRUCTIONS:
1. Read the 'NEW MESSAGES TO INTEGRATE'.
2. Identify the core topic (e.g., 'Programming', 'Shopping', 'Personal Preferences').
3. Evaluate the information density of the new messages. If they consist entirely of conversational filler, small talk, greetings, or acknowledgments with NO substantive facts, projects, preferences, or goals, output EXACTLY the word: SKIP.
4. Otherwise, extract the facts and preferences, merge with any existing memories for that category, and output a valid JSON containing:
   - "category": Short name of the topic category.
   - "memory_type": One of: "preference", "project", "goal", "coding", "personal", "general".
   - "summary": A concise 2-3 sentence merged summary.
   - "entities": Array of key terms, libraries, or technologies discussed.
   - "importance": Integer score 1-10 reflecting the priority of this memory (e.g. basic small talk = 1, coding setup = 7, specific personal preference/intent = 9).

Respond ONLY with either the word SKIP or a valid JSON block enclosed in ```json and ```."""
