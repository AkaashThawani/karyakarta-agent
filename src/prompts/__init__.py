"""
Prompts Package - System prompts and templates

This package contains prompt templates and management for the agent.
"""

# Import prompts
from .system_prompt import SYSTEM_PROMPT, get_system_prompt_with_context

__all__ = [
    'SYSTEM_PROMPT',
    'get_system_prompt_with_context',
]
