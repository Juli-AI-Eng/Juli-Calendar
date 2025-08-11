"""Tools module for Juli Calendar Agent."""

from typing import Optional, Dict, Any
from .manage_productivity import ManageProductivityTool
from .find_and_analyze import FindAndAnalyzeTool
from .check_availability import CheckAvailabilityTool
from .optimize_schedule import OptimizeScheduleTool
from .base import BaseTool

# Tool registry
_TOOLS: Dict[str, BaseTool] = {
    "manage_productivity": ManageProductivityTool(),
    "find_and_analyze": FindAndAnalyzeTool(),
    "check_availability": CheckAvailabilityTool(),
    "optimize_schedule": OptimizeScheduleTool()
}


def get_tool_by_name(tool_name: str) -> Optional[BaseTool]:
    """
    Get a tool instance by its name.
    
    Args:
        tool_name: Name of the tool
        
    Returns:
        Tool instance if found, None otherwise
    """
    return _TOOLS.get(tool_name)


def get_all_tools() -> Dict[str, BaseTool]:
    """
    Get all available tools.
    
    Returns:
        Dictionary of tool name to tool instance
    """
    return _TOOLS.copy()


__all__ = [
    'ManageProductivityTool',
    'FindAndAnalyzeTool', 
    'CheckAvailabilityTool',
    'OptimizeScheduleTool',
    'BaseTool',
    'get_tool_by_name',
    'get_all_tools'
]