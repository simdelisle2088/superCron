import logging
import paramiko
import os
from typing import Optional, List
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logging.getLogger("paramiko").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class SFTPClient:
    """
    A class to handle SFTP operations including connecting, uploading, and downloading files.
    """
    
    def __init__(self, hostname: str, username: str, password: Optional[str] = None, 
                 private_key_path: Optional[str] = None, port: int = 22):
        """
        Initialize SFTP client with connection parameters.
        
        Args:
            hostname: The SFTP server hostname
            username: Username for authentication
            password: Password for authentication (optional if using private key)
            private_key_path: Path to private key file (optional if using password)
            port: Port number (default is 22)
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.private_key_path = private_key_path
        self.port = port
        self.sftp = None
        self.transport = None

    def connect(self) -> None:
        """
        Establish SFTP connection using either password or private key authentication.
        
        Raises:
            paramiko.SSHException: If connection fails
            paramiko.AuthenticationException: If authentication fails
        """
        try:
            self.transport = paramiko.Transport((self.hostname, self.port))
            
            if self.private_key_path:
                private_key = paramiko.RSAKey.from_private_key_file(self.private_key_path)
                self.transport.connect(username=self.username, pkey=private_key)
            else:
                self.transport.connect(username=self.username, password=self.password)
            
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            print(f"Connected to {self.hostname}")
            
        except Exception as e:
            self.close()
            raise Exception(f"Failed to connect to {self.hostname}: {str(e)}")

    def create_directory_recursive(self, remote_path: str) -> None:
        """
        Create a directory and all its parent directories if they don't exist.
        
        Args:
            remote_path: Path to create on the SFTP server
        """
        path_parts = remote_path.split('/')
        current_path = ""
        
        for part in path_parts:
            if part:
                if current_path:
                    current_path = f"{current_path}/{part}"
                else:
                    current_path = part
                    
                try:
                    self.sftp.stat(current_path)
                except IOError:
                    try:
                        self.sftp.mkdir(current_path)
                        logger.info(f"Created directory: {current_path}")
                    except Exception as e:
                        logger.debug(f"Failed to create directory {current_path}: {str(e)}")
    
    def upload_file(self, local_path: str, remote_path: str) -> None:
        """
        Upload a file to the SFTP server.
        
        Args:
            local_path: Path to the local file
            remote_path: Destination path on the SFTP server
        """
        try:
            logger.info(f"Uploading to {remote_path}")
            
            # Verify local file exists
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local file not found: {local_path}")
                
            # Create remote directory structure
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                self.create_directory_recursive(remote_dir)
                
            # Upload file
            self.sftp.put(local_path, remote_path, confirm=True)
            logger.info(f"Successfully uploaded to {remote_path}")
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path} to {remote_path}: {str(e)}")
            raise Exception(f"Failed to upload {local_path}: {str(e)}")

    def download_file(self, remote_path: str, local_path: str) -> None:
        """
        Download a file from the SFTP server.
        
        Args:
            remote_path: Path to the file on the SFTP server
            local_path: Destination path on the local machine
        """
        try:
            self.sftp.get(remote_path, local_path)
            print(f"Downloaded {remote_path} to {local_path}")
        except Exception as e:
            raise Exception(f"Failed to download {remote_path}: {str(e)}")

    def list_directory(self, remote_path: str = '.') -> List[str]:
        """
        List contents of a directory on the SFTP server.
        
        Args:
            remote_path: Path to the directory on the SFTP server
        
        Returns:
            List of items in the directory
        """
        try:
            return self.sftp.listdir(remote_path)
        except Exception as e:
            raise Exception(f"Failed to list directory {remote_path}: {str(e)}")

    def create_directory(self, remote_path: str) -> None:
        """
        Create a directory on the SFTP server.
        
        Args:
            remote_path: Path where the directory should be created
        """
        try:
            self.sftp.mkdir(remote_path)
            print(f"Created directory {remote_path}")
        except Exception as e:
            raise Exception(f"Failed to create directory {remote_path}: {str(e)}")

    def remove_file(self, remote_path: str) -> None:
        """
        Remove a file from the SFTP server.
        
        Args:
            remote_path: Path to the file to be removed
        """
        try:
            self.sftp.remove(remote_path)
            print(f"Removed file {remote_path}")
        except Exception as e:
            raise Exception(f"Failed to remove file {remote_path}: {str(e)}")

    def close(self) -> None:
        """Close the SFTP connection and transport."""
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()
        print("Connection closed")


# 
#   EXAMPLE ON HOW TO USE SFTP
# 
# if __name__ == "__main__":
#     # Using password authentication
#     sftp = SFTPClient(
#         hostname="example.com",
#         username="user",
#         password="password"
#     )
    
#     try:
#         # Connect to the server
#         sftp.connect()
        
#         # Upload a file
#         sftp.upload_file("local_file.txt", "/remote/path/file.txt")
        
#         # Download a file
#         sftp.download_file("/remote/path/file.txt", "downloaded_file.txt")
        
#         # List directory contents
#         files = sftp.list_directory("/remote/path")
#         print("Directory contents:", files)
        
#     except Exception as e:
#         print(f"An error occurred: {str(e)}")
        
#     finally:
#         # Always close the connection
#         sftp.close()