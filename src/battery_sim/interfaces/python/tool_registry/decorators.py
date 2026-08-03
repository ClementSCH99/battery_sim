"""Lifecycle metadata for discoverable engineering tools."""

from typing import List, Optional

def agent_tool(
    description: str,
    examples: Optional[List[str]] = None,
    maturity: str = "experimental",
):
    """
    Decorator to mark a method as an LLM-accessible tool.
    
    TEACHING: This is how we tell the LLM "this method can be called."
    The decorator attaches metadata (description, examples) so the LLM
    knows what the tool does before calling it.
    
    Args:
        description: One-sentence description of what the tool does
        examples: List of example usage strings
        maturity: ``core`` for reviewed first-product capabilities, otherwise
            ``experimental`` until physical assumptions are reviewed.
    """
    if maturity not in {"core", "experimental", "legacy"}:
        raise ValueError(f"Unsupported tool maturity: {maturity}")
    def decorator(func):
        func._is_agent_tool = True
        func._tool_description = description
        func._tool_examples = examples or []
        func._tool_maturity = maturity
        return func
    return decorator
