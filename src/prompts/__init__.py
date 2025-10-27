"""
Prompts Package - System prompts and templates

This package contains prompt templates and management for the agent.
"""

# Import prompts
from .system_prompt import SYSTEM_PROMPT, get_system_prompt_with_context
from .reason_agent_prompt import (
    REASON_AGENT_PROMPT,
    get_reason_agent_prompt,
    get_reason_agent_prompt_with_context
)
from .executor_agent_prompt import (
    EXECUTOR_AGENT_PROMPT,
    get_executor_agent_prompt,
    get_executor_agent_general_prompt,
    get_executor_agent_prompt_with_context
)

__all__ = [
    # Base system prompt
    'SYSTEM_PROMPT',
    'get_system_prompt_with_context',
    
    # Reason agent prompts
    'REASON_AGENT_PROMPT',
    'get_reason_agent_prompt',
    'get_reason_agent_prompt_with_context',
    
    # Executor agent prompts
    'EXECUTOR_AGENT_PROMPT',
    'get_executor_agent_prompt',
    'get_executor_agent_general_prompt',
    'get_executor_agent_prompt_with_context',
]
