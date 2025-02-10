from ftplib import FTP
import os
from typing import Optional, List
from pathlib import Path

class FTPClient:
    """
    A class to handle FTP operations including connecting, uploading, and downloading files.
    """
    
    def __init__(self, hostname: str, username: str = '', password: str = '', 
                 port: int = 21, passive_mode: bool = True):
        """
        Initialize FTP client with connection parameters.
        
        Args:
            hostname: The FTP server hostname
            username: Username for authentication (empty for anonymous)
            password: Password for authentication (empty for anonymous)
            port: Port number (default is 21)
            passive_mode: Whether to use passive mode (default True)
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self.passive_mode = passive_mode
        self.ftp = None

    def connect(self) -> None:
        """
        Establish FTP connection and login.
        
        Raises:
            ftplib.all_errors: If connection or login fails
        """
        try:
            self.ftp = FTP()
            self.ftp.connect(self.hostname, self.port)
            self.ftp.login(self.username, self.password)
            self.ftp.set_pasv(self.passive_mode)
            print(f"Connected to {self.hostname}")
            print(self.ftp.getwelcome())
            
        except Exception as e:
            self.close()
            raise Exception(f"Failed to connect to {self.hostname}: {str(e)}")

    def upload_file(self, local_path: str, remote_path: str) -> None:
        """
        Upload a file to the FTP server.
        
        Args:
            local_path: Path to the local file
            remote_path: Destination path on the FTP server
        """
        try:
            with open(local_path, 'rb') as file:
                self.ftp.storbinary(f'STOR {remote_path}', file)
            print(f"Uploaded {local_path} to {remote_path}")
        except Exception as e:
            raise Exception(f"Failed to upload {local_path}: {str(e)}")

    def upload_text_file(self, local_path: str, remote_path: str, encoding: str = 'utf-8') -> None:
        """
        Upload a text file to the FTP server with specific encoding.
        
        Args:
            local_path: Path to the local file
            remote_path: Destination path on the FTP server
            encoding: Text encoding (default utf-8)
        """
        try:
            with open(local_path, 'r', encoding=encoding) as file:
                self.ftp.storlines(f'STOR {remote_path}', file)
            print(f"Uploaded text file {local_path} to {remote_path}")
        except Exception as e:
            raise Exception(f"Failed to upload text file {local_path}: {str(e)}")

    def download_file(self, remote_path: str, local_path: str) -> None:
        """
        Download a file from the FTP server.
        
        Args:
            remote_path: Path to the file on the FTP server
            local_path: Destination path on the local machine
        """
        try:
            with open(local_path, 'wb') as file:
                self.ftp.retrbinary(f'RETR {remote_path}', file.write)
            print(f"Downloaded {remote_path} to {local_path}")
        except Exception as e:
            raise Exception(f"Failed to download {remote_path}: {str(e)}")

    def download_text_file(self, remote_path: str, local_path: str, encoding: str = 'utf-8') -> None:
        """
        Download a text file from the FTP server with specific encoding.
        
        Args:
            remote_path: Path to the file on the FTP server
            local_path: Destination path on the local machine
            encoding: Text encoding (default utf-8)
        """
        try:
            with open(local_path, 'w', encoding=encoding) as file:
                def write_line(line):
                    file.write(line.decode(encoding) + '\n')
                self.ftp.retrlines(f'RETR {remote_path}', write_line)
            print(f"Downloaded text file {remote_path} to {local_path}")
        except Exception as e:
            raise Exception(f"Failed to download text file {remote_path}: {str(e)}")

    def list_directory(self, remote_path: str = '.') -> List[str]:
        """
        List contents of a directory on the FTP server.
        
        Args:
            remote_path: Path to the directory on the FTP server
        
        Returns:
            List of items in the directory
        """
        try:
            return self.ftp.nlst(remote_path)
        except Exception as e:
            raise Exception(f"Failed to list directory {remote_path}: {str(e)}")

    def list_directory_details(self, remote_path: str = '.') -> List[str]:
        """
        List detailed contents of a directory on the FTP server.
        
        Args:
            remote_path: Path to the directory on the FTP server
        
        Returns:
            List of detailed directory entries
        """
        try:
            lines = []
            self.ftp.dir(remote_path, lines.append)
            return lines
        except Exception as e:
            raise Exception(f"Failed to list directory details {remote_path}: {str(e)}")

    def create_directory(self, remote_path: str) -> None:
        """
        Create a directory on the FTP server.
        
        Args:
            remote_path: Path where the directory should be created
        """
        try:
            self.ftp.mkd(remote_path)
            print(f"Created directory {remote_path}")
        except Exception as e:
            raise Exception(f"Failed to create directory {remote_path}: {str(e)}")

    def remove_file(self, remote_path: str) -> None:
        """
        Remove a file from the FTP server.
        
        Args:
            remote_path: Path to the file to be removed
        """
        try:
            self.ftp.delete(remote_path)
            print(f"Removed file {remote_path}")
        except Exception as e:
            raise Exception(f"Failed to remove file {remote_path}: {str(e)}")

    def remove_directory(self, remote_path: str) -> None:
        """
        Remove a directory from the FTP server.
        
        Args:
            remote_path: Path to the directory to be removed
        """
        try:
            self.ftp.rmd(remote_path)
            print(f"Removed directory {remote_path}")
        except Exception as e:
            raise Exception(f"Failed to remove directory {remote_path}: {str(e)}")

    def close(self) -> None:
        """Close the FTP connection."""
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                self.ftp.close()
        print("Connection closed")

# 
#   EXAMPLE ON HOW TO USE SFTP
# 
# if __name__ == "__main__":
#     # Regular authentication
#     ftp = FTPClient(
#         hostname="ftp.example.com",
#         username="user",
#         password="password"
#     )
    
#     # Or anonymous access
#     anonymous_ftp = FTPClient(
#         hostname="ftp.example.com"  # username and password default to empty strings
#     )
    
#     try:
#         # Connect to the server
#         ftp.connect()
        
#         # Upload binary and text files
#         ftp.upload_file("local_binary_file.zip", "remote_file.zip")
#         ftp.upload_text_file("local_text_file.txt", "remote_file.txt")
        
#         # Download binary and text files
#         ftp.download_file("remote_file.zip", "downloaded_file.zip")
#         ftp.download_text_file("remote_file.txt", "downloaded_file.txt")
        
#         # List directory contents
#         files = ftp.list_directory("/remote/path")
#         print("Directory contents:", files)
        
#         # Get detailed directory listing
#         details = ftp.list_directory_details("/remote/path")
#         print("Detailed directory contents:", details)
        
#     except Exception as e:
#         print(f"An error occurred: {str(e)}")
        
#     finally:
#         # Always close the connection
#         ftp.close()