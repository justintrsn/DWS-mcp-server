"""MCP Test Client Framework

A modular testing framework for MCP (Model Context Protocol) servers
with layered abstractions for tool testing, query routing, and scenario execution.
"""

from .base_test_mcp import BaseTestMCP, TestResult

__all__ = [
    'BaseTestMCP',
    'TestResult'
]