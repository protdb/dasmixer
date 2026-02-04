"""Mixin for identification tool operations."""

from ..dataclasses import Tool
from utils.logger import logger


class ToolMixin:
    """
    Mixin providing identification tool management methods.
    
    Requires ProjectBase functionality (_execute, _fetchone, _fetchall, 
    _serialize_json, _deserialize_json, save).
    """
    
    async def add_tool(
        self,
        name: str,
        type: str,  # "Library" or "De Novo"
        parser: str,  # Parser name
        settings: dict | None = None,
        display_color: str | None = None
    ) -> Tool:
        """
        Add a new identification tool.
        
        Args:
            name: Tool name (unique)
            type: Tool type - "Library" or "De Novo"
            parser: Parser name (e.g., "PowerNovo2", "MaxQuant")
            settings: Tool-specific settings (JSON)
            display_color: Color for UI display
            
        Returns:
            Created Tool object
        """
        # Check if exists
        existing = await self._fetchone(
            "SELECT id FROM tool WHERE name = ?",
            (name,)
        )
        if existing:
            raise ValueError(f"Tool with name '{name}' already exists")
        
        settings_json = self._serialize_json(settings)
        
        cursor = await self._execute(
            "INSERT INTO tool (name, type, parser, settings, display_color) VALUES (?, ?, ?, ?, ?)",
            (name, type, parser, settings_json, display_color)
        )
        
        tool_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added tool: {name} (id={tool_id}, type={type}, parser={parser})")
        
        return Tool(
            id=tool_id,
            name=name,
            type=type,
            parser=parser,
            settings=settings,
            display_color=display_color
        )
    
    async def get_tools(self) -> list[Tool]:
        """Get all tools."""
        rows = await self._fetchall("SELECT * FROM tool ORDER BY name")
        return [Tool.from_dict(row) for row in rows]
    
    async def get_tool(self, tool_id: int) -> Tool | None:
        """Get tool by ID."""
        row = await self._fetchone(
            "SELECT * FROM tool WHERE id = ?",
            (tool_id,)
        )
        return Tool.from_dict(row) if row else None
    
    async def update_tool(self, tool: Tool) -> None:
        """Update existing tool."""
        if tool.id is None:
            raise ValueError("Cannot update tool without ID")
        
        settings_json = self._serialize_json(tool.settings)
        
        await self._execute(
            "UPDATE tool SET name = ?, type = ?, parser = ?, settings = ?, display_color = ? WHERE id = ?",
            (tool.name, tool.type, tool.parser, settings_json, tool.display_color, tool.id)
        )
        await self.save()
        logger.debug(f"Updated tool: {tool.name}")
    
    async def delete_tool(self, tool_id: int) -> None:
        """Delete tool (if no identifications associated)."""
        # Check for associated identifications
        count_row = await self._fetchone(
            "SELECT COUNT(*) as cnt FROM identification WHERE tool_id = ?",
            (tool_id,)
        )
        
        if count_row and count_row['cnt'] > 0:
            raise ValueError(
                f"Cannot delete tool: {count_row['cnt']} identifications are associated with it"
            )
        
        await self._execute("DELETE FROM tool WHERE id = ?", (tool_id,))
        await self.save()
        logger.info(f"Deleted tool id={tool_id}")
