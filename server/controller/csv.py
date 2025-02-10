import csv
import os
from typing import List, Dict, Any, Optional

class CSVHandler:
    """
    A flexible class for handling CSV file operations with various customization options.
    """
    
    def __init__(self, filename: str, headers: Optional[List[str]] = None):
        """
        Initialize the CSV handler.
        
        Args:
            filename (str): Name of the CSV file
            headers (List[str], optional): List of column headers
        """
        self.filename = filename
        self.headers = headers
        self.data: List[Dict[str, Any]] = []
        self.file_exists = os.path.exists(filename)
        
    def add_row(self, row_data: Dict[str, Any]) -> None:
        """
        Add a single row to the CSV data.
        
        Args:
            row_data (Dict[str, Any]): Dictionary containing row data
        
        Raises:
            ValueError: If headers are defined and row_data keys don't match
        """
        if self.headers and set(row_data.keys()) != set(self.headers):
            raise ValueError(f"Row data keys must match headers: {self.headers}")
        self.data.append(row_data)
        
    def add_rows(self, rows: List[Dict[str, Any]]) -> None:
        """
        Add multiple rows to the CSV data.
        
        Args:
            rows (List[Dict[str, Any]]): List of dictionaries containing row data
        """
        for row in rows:
            self.add_row(row)
            
    def update_row(self, index: int, row_data: Dict[str, Any]) -> None:
        """
        Update a specific row in the CSV data.
        
        Args:
            index (int): Index of the row to update
            row_data (Dict[str, Any]): New row data
            
        Raises:
            IndexError: If index is out of range
        """
        if index < 0 or index >= len(self.data):
            raise IndexError("Row index out of range")
        if self.headers and set(row_data.keys()) != set(self.headers):
            raise ValueError(f"Row data keys must match headers: {self.headers}")
        self.data[index] = row_data
        
    def delete_row(self, index: int) -> None:
        """
        Delete a specific row from the CSV data.
        
        Args:
            index (int): Index of the row to delete
            
        Raises:
            IndexError: If index is out of range
        """
        if index < 0 or index >= len(self.data):
            raise IndexError("Row index out of range")
        self.data.pop(index)
        
    def save(self, encoding: str = 'utf-8-sig', mode: str = 'w') -> None:
        """
        Save the data to the CSV file in Excel-compatible format.
        
        Args:
            encoding (str): File encoding (default: 'utf-8-sig')
            mode (str): File open mode (default: 'w')
        """
        headers = self.headers or (self.data[0].keys() if self.data else [])
        
        with open(self.filename, mode=mode, newline='', encoding=encoding) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=headers,
                delimiter=',',
                quoting=csv.QUOTE_MINIMAL
            )
            writer.writeheader()
            writer.writerows(self.data)

            
    def load(self, encoding: str = 'utf-8') -> None:
        """
        Load data from the CSV file.
        
        Args:
            encoding (str): File encoding (default: 'utf-8')
            
        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        if not self.file_exists:
            raise FileNotFoundError(f"File {self.filename} not found")
            
        with open(self.filename, mode='r', encoding=encoding) as file:
            reader = csv.DictReader(file)
            self.headers = reader.fieldnames
            self.data = [row for row in reader]
            
    def get_column(self, column_name: str) -> List[Any]:
        """
        Get all values from a specific column.
        
        Args:
            column_name (str): Name of the column
            
        Returns:
            List[Any]: List of values from the specified column
            
        Raises:
            KeyError: If column_name doesn't exist
        """
        if not self.headers or column_name not in self.headers:
            raise KeyError(f"Column {column_name} not found")
        return [row[column_name] for row in self.data]
    
    def add_column(self, column_name: str, default_value: Any = None) -> None:
        """
        Add a new column to the CSV data.
        
        Args:
            column_name (str): Name of the new column
            default_value (Any, optional): Default value for existing rows
        """
        if not self.headers:
            self.headers = list(self.data[0].keys()) if self.data else []
        
        if column_name not in self.headers:
            self.headers.append(column_name)
            for row in self.data:
                row[column_name] = default_value
                
    def get_row(self, index: int) -> Dict[str, Any]:
        """
        Get a specific row from the CSV data.
        
        Args:
            index (int): Index of the row
            
        Returns:
            Dict[str, Any]: Row data
            
        Raises:
            IndexError: If index is out of range
        """
        if index < 0 or index >= len(self.data):
            raise IndexError("Row index out of range")
        return self.data[index]