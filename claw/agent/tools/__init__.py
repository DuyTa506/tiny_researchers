"""Agent tools for Claw Researcher."""

from claw.agent.tools.base import Tool
from claw.agent.tools.code_gen import CodeGenTool
from claw.agent.tools.dataset_search import DatasetSearchTool
from claw.agent.tools.exec_tool import ExecTool
from claw.agent.tools.filesystem import ListDirTool, ReadFileTool, WriteFileTool
from claw.agent.tools.paper_read import PaperReadTool
from claw.agent.tools.paper_search import PaperSearchTool
from claw.agent.tools.registry import ToolRegistry
from claw.agent.tools.web import WebFetchTool, WebSearchTool

__all__ = [
    "Tool",
    "ToolRegistry",
    # Research tools
    "PaperSearchTool",
    "PaperReadTool",
    "DatasetSearchTool",
    # Web tools
    "WebSearchTool",
    "WebFetchTool",
    # Filesystem tools
    "ReadFileTool",
    "WriteFileTool",
    "ListDirTool",
    # Execution tool
    "ExecTool",
    # Code generation tool
    "CodeGenTool",
]
