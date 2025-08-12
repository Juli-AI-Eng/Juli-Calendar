"""Base class for A2A tools."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseTool(ABC):
    """Base class for all A2A tools."""
    
    def __init__(self):
        """Initialize the tool."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the tool description."""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get the tool's input schema."""
        pass
    
    @abstractmethod
    def validate_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and process input data."""
        pass
    
    @abstractmethod
    async def execute(self, data: Dict[str, Any], credentials: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Execute the tool with given data and credentials."""
        pass