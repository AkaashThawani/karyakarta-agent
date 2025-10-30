"""
Excel Export Tool

Exports structured data to Excel files (.xlsx format).
Supports lists of dictionaries, pandas DataFrames, and nested data.

Example:
    data = [
        {"rank": 1, "song": "Flowers", "artist": "Miley Cyrus"},
        {"rank": 2, "song": "Kill Bill", "artist": "SZA"}
    ]
    
    tool = ExcelExportTool()
    result = tool.execute(data=data, filename="top_songs")
    # Creates: top_songs.xlsx
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import pandas as pd
from pathlib import Path
import json

from src.tools.base import BaseTool, ToolResult
from src.services.logging_service import LoggingService


class ExcelExportInput(BaseModel):
    """Input schema for Excel export."""
    data: Any = Field(
        description="Data to export (list of dicts, dict, or JSON string)"
    )
    filename: str = Field(
        description="Output filename (without extension)"
    )
    sheet_name: Optional[str] = Field(
        default="Sheet1",
        description="Name of the Excel sheet"
    )
    output_dir: Optional[str] = Field(
        default="exports",
        description="Output directory for the file"
    )


class ExcelExportTool(BaseTool):
    """
    Export data to Excel files.
    
    Features:
    - Exports lists of dictionaries to Excel
    - Handles nested data (flattens if needed)
    - Auto-creates output directory
    - Returns file path for download
    """
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None):
        super().__init__(logger)
        self.session_id = session_id
    
    @property
    def name(self) -> str:
        return "excel_export"
    
    @property
    def description(self) -> str:
        return """Export structured data to Excel (.xlsx) files.
        
        Supports:
        - Lists of dictionaries (most common)
        - Single dictionaries
        - Nested data (auto-flattened)
        - JSON strings
        
        Example Usage:
        1. Export song list:
           data = [{"song": "Flowers", "artist": "Miley Cyrus"}]
           filename = "top_songs"
           
        2. Export with custom sheet name:
           sheet_name = "Top 10 Songs This Week"
           
        Returns: Path to created Excel file
        """
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        data = kwargs.get("data")
        filename = kwargs.get("filename")
        
        return bool(data is not None and filename)
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        data = kwargs.get("data")
        filename = kwargs.get("filename")
        sheet_name = kwargs.get("sheet_name", "Sheet1")
        output_dir = kwargs.get("output_dir", "exports")
        
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Convert data to DataFrame
            df = self._prepare_dataframe(data)
            
            if df is None or df.empty:
                return ToolResult(
                    success=False,
                    error="No data to export or invalid data format",
                    metadata={}
                )
            
            # Generate full file path
            file_path = output_path / f"{filename}.xlsx"
            
            # Export to Excel
            df.to_excel(file_path, sheet_name=sheet_name, index=False, engine='openpyxl')
            
            if self.logger:
                self.logger.status(f"✅ Exported {len(df)} rows to {file_path}")
            
            return ToolResult(
                success=True,
                data=f"Exported to {file_path}",
                metadata={
                    "file_path": str(file_path),
                    "rows": len(df),
                    "columns": list(df.columns),
                    "sheet_name": sheet_name
                }
            )
            
        except Exception as e:
            error_msg = f"Excel export failed: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            
            return ToolResult(
                success=False,
                error=error_msg,
                metadata={}
            )
    
    def _prepare_dataframe(self, data: Any) -> Optional[pd.DataFrame]:
        """
        Convert various data formats to pandas DataFrame.
        
        Args:
            data: Input data in various formats
            
        Returns:
            pandas DataFrame or None
        """
        # Handle None
        if data is None:
            return None
        
        # Handle JSON string
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return None
        
        # Handle list of dictionaries (most common)
        if isinstance(data, list):
            if not data:
                return None
            
            # Check if list of dicts
            if all(isinstance(item, dict) for item in data):
                return pd.DataFrame(data)
            
            # Try to convert anyway
            try:
                return pd.DataFrame(data)
            except:
                return None
        
        # Handle single dictionary
        if isinstance(data, dict):
            # Check if it's a dict of lists (columnar format)
            if all(isinstance(v, list) for v in data.values()):
                return pd.DataFrame(data)
            
            # Single record - convert to list
            return pd.DataFrame([data])
        
        # Handle DataFrame
        if isinstance(data, pd.DataFrame):
            return data
        
        return None
    
    def as_langchain_tool(self):
        tool_instance = self
        
        @tool(args_schema=ExcelExportInput)
        def excel_export(
            data: Any,
            filename: str,
            sheet_name: Optional[str] = "Sheet1",
            output_dir: Optional[str] = "exports"
        ) -> str:
            """Export data to Excel file."""
            result = tool_instance.execute(
                data=data,
                filename=filename,
                sheet_name=sheet_name,
                output_dir=output_dir
            )
            return tool_instance.format_result(result)
        
        return excel_export


class CSVExportTool(BaseTool):
    """
    Export data to CSV files (simpler alternative to Excel).
    """
    
    def __init__(self, session_id: str = "default", logger: Optional[LoggingService] = None):
        super().__init__(logger)
        self.session_id = session_id
    
    @property
    def name(self) -> str:
        return "csv_export"
    
    @property
    def description(self) -> str:
        return "Export structured data to CSV files."
    
    def validate_params(self, **kwargs) -> bool:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        data = kwargs.get("data")
        filename = kwargs.get("filename")
        
        return bool(data is not None and filename)
    
    def _execute_impl(self, **kwargs) -> ToolResult:
        if "kwargs" in kwargs:
            kwargs = kwargs["kwargs"]
        
        data = kwargs.get("data")
        filename = kwargs.get("filename")
        output_dir = kwargs.get("output_dir", "exports")
        
        try:
            # Create output directory
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Convert to DataFrame
            if isinstance(data, str):
                data = json.loads(data)
            
            if isinstance(data, list) and data:
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                return ToolResult(success=False, error="Invalid data format", metadata={})
            
            # Generate file path
            file_path = output_path / f"{filename}.csv"
            
            # Export to CSV
            df.to_csv(file_path, index=False)
            
            if self.logger:
                self.logger.status(f"✅ Exported {len(df)} rows to {file_path}")
            
            return ToolResult(
                success=True,
                data=f"Exported to {file_path}",
                metadata={
                    "file_path": str(file_path),
                    "rows": len(df),
                    "columns": list(df.columns)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"CSV export failed: {str(e)}",
                metadata={}
            )
