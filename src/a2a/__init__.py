"""A2A (Agent-to-Agent) protocol implementation for Juli Calendar Agent."""

from .handlers import (
    get_agent_card,
    get_credentials_manifest,
    handle_rpc_request,
    authenticate_agent
)

__all__ = [
    'get_agent_card',
    'get_credentials_manifest', 
    'handle_rpc_request',
    'authenticate_agent'
]