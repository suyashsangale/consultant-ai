"""
Unified LLM wrapper — abstracts Anthropic vs Groq provider differences.

Usage:
    from app.llm import call_llm

    text = call_llm(
        system="You are ...",          # None if no system prompt
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=1500,
        use_doc_model=False,           # True → cheaper/faster model (haiku-equivalent)
    )

Set LLM_PROVIDER=groq in .env and add GROQ_API_KEY to use Groq's free tier.
"""
from app.config import get_settings

settings = get_settings()


def call_llm(
    *,
    system: str | None,
    messages: list[dict],
    max_tokens: int,
    use_doc_model: bool = False,
    json_mode: bool = False,
) -> str:
    """
    Call the configured LLM provider and return the raw text response.

    Args:
        system:        System prompt (None to omit).
        messages:      List of {"role": ..., "content": ...} dicts.
        max_tokens:    Maximum tokens in the response.
        use_doc_model: When True, use the lighter/cheaper model (for document
                       summarisation); when False, use the full chat model.
    """
    provider = settings.llm_provider.lower()

    if provider == "groq":
        return _call_groq(system=system, messages=messages, max_tokens=max_tokens, use_doc_model=use_doc_model, json_mode=json_mode)
    else:
        return _call_anthropic(system=system, messages=messages, max_tokens=max_tokens, use_doc_model=use_doc_model)


def _call_anthropic(
    *,
    system: str | None,
    messages: list[dict],
    max_tokens: int,
    use_doc_model: bool,
) -> str:
    import anthropic

    model = "claude-haiku-4-5-20251001" if use_doc_model else "claude-sonnet-4-20250514"
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(**kwargs)
    return response.content[0].text


def _call_groq(
    *,
    system: str | None,
    messages: list[dict],
    max_tokens: int,
    use_doc_model: bool,
    json_mode: bool = False,
) -> str:
    from groq import Groq

    model = settings.groq_doc_model if use_doc_model else settings.groq_chat_model

    # Groq uses OpenAI-style messages — inject system as first message
    full_messages: list[dict] = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)

    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": full_messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content
