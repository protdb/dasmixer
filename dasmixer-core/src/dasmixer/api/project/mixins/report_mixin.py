"""Report-related methods for Project."""

from typing import Optional


class ReportMixin:
    """Methods for working with reports in Project."""
    
    async def get_generated_reports(self, report_name: Optional[str] = None) -> list[dict]:
        """
        Get list of generated reports.
        
        Args:
            report_name: Filter by report name (optional)
            
        Returns:
            list[dict]: List of records with metadata
        """
        if report_name:
            query = """
                SELECT id, report_name, created_at, 
                       project_settings, tools_settings, report_settings
                FROM generated_reports
                WHERE report_name = ?
                ORDER BY created_at DESC
            """
            rows = await self._fetchall(query, (report_name,))
        else:
            query = """
                SELECT id, report_name, created_at,
                       project_settings, tools_settings, report_settings
                FROM generated_reports
                ORDER BY created_at DESC
            """
            rows = await self._fetchall(query)
        
        return [dict(row) for row in rows]
    
    async def delete_generated_report(self, report_id: int) -> None:
        """
        Delete a generated report.
        
        Args:
            report_id: ID in generated_reports table
        """
        await self._execute("DELETE FROM generated_reports WHERE id = ?", (report_id,))
        await self.save()
    
    async def save_report_parameters(self, report_name: str, parameters: str) -> None:
        """
        Save report parameters.
        
        Args:
            report_name: Report name
            parameters: Parameters in format "key1=value1\nkey2=value2"
        """
        await self._execute(
            """
            INSERT OR REPLACE INTO report_parameters (report_name, parameters)
            VALUES (?, ?)
            """,
            (report_name, parameters)
        )
        await self.save()
    
    async def get_report_parameters(self, report_name: str) -> Optional[str]:
        """
        Get saved report parameters.
        
        Args:
            report_name: Report name
            
        Returns:
            Parameters string or None
        """
        row = await self._fetchone(
            "SELECT parameters FROM report_parameters WHERE report_name = ?",
            (report_name,)
        )
        return row['parameters'] if row else None
