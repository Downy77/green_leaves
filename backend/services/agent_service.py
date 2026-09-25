from functools import lru_cache

from backend.agents.runtime import CouplingAgentRuntime

from .storage import SQLiteAgentStore


@lru_cache(maxsize=1)
def get_agent_runtime() -> CouplingAgentRuntime:
    return CouplingAgentRuntime(SQLiteAgentStore())
