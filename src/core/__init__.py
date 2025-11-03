"""
Core Package - Agent orchestration, configuration, and workflow management

This package contains the core functionality of the KaryaKarta Agent system.
"""

# Import core components
from .config import settings
from .memory import MemoryService, get_memory_service

# Lazy import to avoid circular dependency
def __getattr__(name):
    if name == 'AgentManager':
        from .agent import AgentManager
        return AgentManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'settings',
    'AgentManager',
    'MemoryService',
    'get_memory_service',
]
