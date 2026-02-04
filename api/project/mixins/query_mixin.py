"""Mixin for low-level SQL query operations."""

import pandas as pd


class QueryMixin:
    """
    Mixin providing low-level SQL query methods.
    
    For complex reports and custom operations.
    Requires ProjectBase functionality (_fetchall).
    """
    
    async def execute_query(
        self,
        query: str,
        params: tuple | dict | None = None
    ) -> list[dict]:
        """
        Execute raw SQL query.
        
        For complex reports and custom operations.
        
        Args:
            query: SQL query string
            params: Query parameters (tuple or dict)
        
        Returns:
            List of rows as dictionaries
        """
        return await self._fetchall(query, params)
    
    async def execute_query_df(
        self,
        query: str,
        params: tuple | dict | None = None
    ) -> pd.DataFrame:
        """
        Execute query and return as DataFrame.
        
        Args:
            query: SQL query string
            params: Query parameters (tuple or dict)
        
        Returns:
            DataFrame with query results
        """
        rows = await self._fetchall(query, params)
        return pd.DataFrame(rows) if rows else pd.DataFrame()
