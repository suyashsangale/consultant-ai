"""
Core knowledge engine:
  - deep_merge: non-destructively merges new KB facts into existing KB
  - build_system_prompt: assembles the full Claude system prompt from KB + RAG context
"""

KB_CATEGORIES = [
    "overview", "products", "customers", "revenue",
    "team", "competition", "history", "now", "future", "ops",
]

HAT_PERSONAS = {
    "cfo": (
        "You are operating in CFO mode. Focus on financials, unit economics, burn rate, "
        "revenue model, funding, and financial risk. Reference specific financial facts "
        "from the knowledge base and any uploaded documents in every answer."
    ),
    "marketer": (
        "You are operating in Marketing Strategist mode. Focus on positioning, ICP, "
        "acquisition channels, messaging, brand, and growth loops. Be creative but grounded "
        "in the specific business context."
    ),
    "ops": (
        "You are operating in Operations Advisor mode. Focus on processes, efficiency, "
        "tooling, team structure, vendors, and execution. Be concrete and actionable."
    ),
    "hr": (
        "You are operating in People & Culture mode. Focus on hiring, team structure, "
        "performance, culture, and retention. Reference the team size and stage from context."
    ),
    "strategy": (
        "You are operating in Strategy mode. Focus on big-picture positioning, competitive "
        "moats, long-term bets, and prioritisation trade-offs."
    ),
}


def deep_merge(base: dict, updates: dict) -> dict:
    """
    Recursively merges `updates` into `base`.
    Never overwrites existing values with empty ones.
    Nested dicts are merged recursively. Lists are replaced.
    """
    result = dict(base)
    for key, value in updates.items():
        if value is None or value == "" or value == {} or value == []:
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def build_system_prompt(
    kb: dict,
    business_name: str,
    hat: str = "auto",
    doc_context: list[dict] | None = None,
) -> str:
    """
    Assembles the full system prompt for Claude.

    Args:
        kb:           The business's knowledge base dict
        business_name: Business name string
        hat:          Active mode — auto | cfo | marketer | ops | hr | strategy
        doc_context:  List of {content, filename, similarity} dicts from RAG search
    """
    filled  = [c for c in KB_CATEGORIES if kb.get(c)]
    missing = [c for c in KB_CATEGORIES if not kb.get(c)]

    hat_section = ""
    if hat in HAT_PERSONAS:
        hat_section = f"\nCURRENT MODE: {hat.upper()}\n{HAT_PERSONAS[hat]}\n"

    # Format RAG context section
    rag_section = ""
    if doc_context:
        rag_lines = ["\nRELEVANT DOCUMENT CONTEXT (retrieved for this query):"]
        for chunk in doc_context:
            sim_pct = int(chunk["similarity"] * 100)
            rag_lines.append(
                f"\n--- From \"{chunk['filename']}\" (relevance: {sim_pct}%) ---\n"
                f"{chunk['content']}\n---"
            )
        rag_section = "\n".join(rag_lines)

    prompt = f"""You are the dedicated AI Business Buddy for {business_name or "this business"}.
You are a strategic partner — not a generic assistant. Every response must be grounded in what you know about this specific business.
{hat_section}
CURRENT KNOWLEDGE BASE:
{_format_kb(kb)}

KNOWN CATEGORIES: {", ".join(filled) if filled else "none yet"}
MISSING CATEGORIES: {", ".join(missing)}
{rag_section}

ABSOLUTE RULES:
1. NEVER give generic advice. If you lack specific context, say exactly what is missing and ask ONE focused question to get it.
2. ALWAYS extract new facts from every user message and return them in knowledge_updates.
3. When you learn something new, confirm it: "Got it — I've noted that [specific fact]."
4. DISCOVERY phase: ask one focused question per message to fill the biggest gap. Briefly explain why you are asking.
5. CONSULTING phase: lead with a sharp insight referencing known facts ("Given that your X is Y..."). Ask follow-up only when genuinely needed.
6. Switch to consulting phase when overview + products + customers + now are all filled.
7. NEVER say "it depends" without immediately stating what it depends on and asking for that information.
8. If relevant document context is provided above, cite it specifically ("According to your [filename]...").
9. If a question cannot be answered well without a specific missing fact — stop and ask for it.

RESPONSE FORMAT — return ONLY valid JSON, no markdown fences, no text outside:
{{
  "reply": "your response here — markdown supported",
  "knowledge_updates": {{
    "overview": {{}}, "products": {{}}, "customers": {{}}, "revenue": {{}},
    "team": {{}}, "competition": {{}}, "history": {{}}, "now": {{}}, "future": {{}}, "ops": {{}}
  }},
  "phase": "discovery",
  "knowledge_gaps": ["up to 4 specific things still needed"],
  "detected_hat": "auto | cfo | marketer | ops | hr | strategy"
}}

Only include categories in knowledge_updates that have NEW info from this message.
Use short, factual string values — not sentences.
{"Start with a warm 2-sentence intro and ask for the business name and what it does." if not kb else "Continue the conversation, building on everything you already know."}
"""
    return prompt


def _format_kb(kb: dict) -> str:
    if not kb:
        return "(empty — no knowledge gathered yet)"
    lines = []
    for cat in KB_CATEGORIES:
        if kb.get(cat):
            lines.append(f"  {cat}:")
            for k, v in kb[cat].items():
                lines.append(f"    {k}: {v}")
    return "\n".join(lines) if lines else "(empty)"


def detect_hat(message: str) -> str:
    """Simple keyword classifier for hat mode."""
    m = message.lower()
    if any(w in m for w in ["revenue", "burn", "profit", "financial", "funding", "cash", "budget", "cost", "margin", "cfo", "p&l"]):
        return "cfo"
    if any(w in m for w in ["market", "brand", "customer", "acquire", "channel", "campaign", "seo", "ads", "growth", "funnel"]):
        return "marketer"
    if any(w in m for w in ["process", "operation", "workflow", "vendor", "tool", "system", "scale", "ops", "automation"]):
        return "ops"
    if any(w in m for w in ["hire", "team", "culture", "employee", "salary", "retention", "hr", "people", "onboard"]):
        return "hr"
    return "auto"
