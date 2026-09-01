"""Agent context and prompt template utilities for the LME report skill.

Provides the Context model for runtime data binding and a helper to
construct LangChain ChatPromptTemplate instances from keyword arguments.
"""

from .context import Context, build_standard_chat_prompt_template

__all__ = ["Context", "build_standard_chat_prompt_template"]
