"""Agent context and prompt template utilities for the LME report skill.

Provides the Context model for runtime data binding and a helper to
construct LangChain ChatPromptTemplate instances from keyword arguments.
"""

from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    PromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.prompts.image import ImagePromptTemplate
from pydantic import BaseModel


class Context(BaseModel):
    """Runtime context passed to the analysis agent during invocation.

    Attributes:
        directory: Path to the folder containing data files.
        schema_output: Cached schema analysis result (populated at runtime).
        pandas_output: Cached pandas analysis result (populated at runtime).
    """

    directory: str
    schema_output: str = ""
    pandas_output: str = ""


def build_standard_chat_prompt_template(kwargs):
    """Build a LangChain ChatPromptTemplate from keyword arguments.

    Supports system and human message templates, including multimodal
    (image) prompts via ImagePromptTemplate.

    Args:
        kwargs: Keyword arguments that may include "system" and "human"
            keys, each containing a dict or list of dicts with prompt
            template configuration.

    Returns:
        ChatPromptTemplate: A LangChain chat prompt template assembled
            from the provided system and human message templates.
    """
    messages = []

    if "system" in kwargs:
        content = kwargs.get("system")

        # allow list of prompts for multimodal
        if isinstance(content, list):
            prompts = [PromptTemplate(**c) for c in content]
        else:
            prompts = [PromptTemplate(**content)]

        message = SystemMessagePromptTemplate(prompt=prompts)
        messages.append(message)

    if "human" in kwargs:
        content = kwargs.get("human")

        # allow list of prompts for multimodal
        if isinstance(content, list):
            prompts = []
            for c in content:
                if c.get("type") == "image":
                    prompts.append(ImagePromptTemplate(**c))
                else:
                    prompts.append(PromptTemplate(**c))
        else:
            if content.get("type") == "image":
                prompts = [ImagePromptTemplate(**content)]
            else:
                prompts = [PromptTemplate(**content)]

        message = HumanMessagePromptTemplate(prompt=prompts)
        messages.append(message)

    chat_prompt_template = ChatPromptTemplate.from_messages(messages)

    return chat_prompt_template
