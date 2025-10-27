"""
Core Package - Agent orchestration, configuration, and workflow management

This package contains the core functionality of the KaryaKarta Agent system.
"""

# Import core components
from .config import settings
from .agent import AgentManager, SimpleAgentManager
from .memory import MemoryService, get_memory_service

__all__ = [
    'settings',
    'AgentManager',
    'SimpleAgentManager',
    'MemoryService',
    'get_memory_service',
]
