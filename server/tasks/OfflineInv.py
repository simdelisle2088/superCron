from datetime import datetime
import logging
import os
from typing import Optional, List, Any
from pathlib import Path

from controller.stores import get_stores
from models.InvModel import InvLocations
from controller.csv import CSVHandler
from controller.email import EmailConfig, EmailService
from controller.sftp import SFTPClient  # Import the SFTP client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from settings import PrimarySessionLocal, get_settings

# Configure logging with a more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

class LocationDataHandler:
    """Handles location-specific data operations"""
    
    def __init__(self):
        self.required_fields = [
            "id", "store", "level", "row", "side", "column",
            "shelf", "bin", "full_location"
        ]
        self.csv_handler = None

    async def fetch_data(self, store_id: str, db: AsyncSession) -> Optional[List[Any]]:
        """Fetch location data for a specific store"""
        result = await db.execute(
            select(InvLocations).where(
                InvLocations.store == store_id,
                InvLocations.is_archived == False
            )
        )
        return result.scalars().all()

    def get_headers(self) -> List[str]:
        """Get headers for location CSV"""
        return [
            "id", "upc", "name", "store", "level", "row", "side", "column",
            "shelf", "bin", "full_location", "updated_by", "updated_at",
            "created_by", "created_at", "is_archived"
        ]

    def get_row_data(self, location: Any) -> dict:
        """Get row data for location CSV"""
        return {
            "id": location.id,
            "upc": location.upc,
            "name": location.name,
            "store": location.store,
            "level": location.level,
            "row": location.row,
            "side": location.side,
            "column": location.column,
            "shelf": location.shelf,
            "bin": location.bin,
            "full_location": location.full_location,
            "updated_by": location.updated_by,
            "updated_at": location.updated_at,
            "created_by": location.created_by,
            "created_at": location.created_at,
            "is_archived": location.is_archived
        }

    def validate_data(self, location: Any) -> List[str]:
        """Validate location data"""
        return [
            field for field in self.required_fields 
            if getattr(location, field, None) is None
        ]

class StoreExportService:
    """Main service that coordinates the export process"""
    
    def __init__(self, email_config: EmailConfig):
        self.email_service = EmailService(email_config)
        self.location_handler = LocationDataHandler()
        # Initialize SFTP client with settings
        self.sftp_client = SFTPClient(
            hostname=settings.nas.hostname,
            username=settings.nas.username,
            password=settings.nas.password,
            port=settings.nas.port
        )

    async def export_store_locations(self, store_id: str, store_name: str, db: AsyncSession) -> str:
        """Export store locations to CSV, send via email and upload to SFTP"""
        try:
            logger.info(f"Starting export for store_id: {store_id}")

            if not store_id or not str(store_id).strip():
                raise ValueError("Store ID cannot be empty")

            # Fetch data
            locations = await self.location_handler.fetch_data(store_id, db)
            if not locations:
                return f"No locations found for store {store_id}."

            # Create a temporary directory for the export using absolute path
            temp_dir = Path.cwd() / "temp_exports"
            temp_dir.mkdir(exist_ok=True)

            # Generate CSV filename and get absolute path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"store_{store_id}_locations_{timestamp}.csv"
            local_file_path = temp_dir.absolute() / csv_filename

            try:
                # Initialize CSV handler with headers
                csv_handler = CSVHandler(
                    filename=str(local_file_path),
                    headers=self.location_handler.get_headers()
                )

                # Add data rows and save
                for location in locations:
                    row_data = self.location_handler.get_row_data(location)
                    missing_fields = self.location_handler.validate_data(location)

                    if missing_fields:
                        logger.warning(f"Missing required fields for location {location.id}: {missing_fields}")
                        continue
                    
                    csv_handler.add_row(row_data)

                # Save CSV
                csv_handler.save()

                try:
                    # Connect to SFTP
                    self.sftp_client.connect()

                    # Format remote path using forward slashes for SFTP
                    remote_path = f"Dev/inventory_backup/{store_name}/{csv_filename}"
                    remote_path = remote_path.replace('\\', '/')  # Ensure forward slashes for SFTP

                    logger.info(f"Attempting to upload file to {remote_path}")

                    # Upload file to SFTP (the create_directory_recursive is handled inside upload_file)
                    self.sftp_client.upload_file(str(local_file_path), remote_path)
                    logger.info(f"CSV file uploaded to SFTP: {remote_path}")

                except Exception as e:
                    logger.error(f"SFTP upload failed: {str(e)}")
                    raise
                finally:
                    self.sftp_client.close()

                # Send email
                subject = f'Inventaire Backup pour {store_name}'
                body = f"""
                Voici les localisations pour le magasin {store_id}.
                Voici les informations suivantes :
                - Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                - Store: {store_id}
                """

                await self.email_service.send_email_with_attachment(
                    subject,
                    body,
                    str(local_file_path)
                )

                return f"CSV file {csv_filename} successfully sent to {self.email_service.config.recipient_email} and uploaded to SFTP"

            finally:
                # Cleanup: remove the file and temp directory if they exist
                if local_file_path.exists():
                    local_file_path.unlink()
                if temp_dir.exists() and not any(temp_dir.iterdir()):
                    temp_dir.rmdir()

        except Exception as e:
            logger.error(f"Export failed for store {store_id}", exc_info=True)
            raise

async def export_store():
    """Main function to handle store export"""
    try:
        stores = get_stores()

        for store in stores:
            # Initialize email configuration
            email_config = EmailConfig(
                recipient_email=settings.db.recipient
            )

            # Create export service
            export_service = StoreExportService(email_config)

            async with PrimarySessionLocal() as session:
                try:
                    result = await export_service.export_store_locations(
                        store.id,
                        store.name,
                        session
                    )
                    logger.info(f"{store.name}: {result}")
                except Exception as e:
                    logger.error(f"Export operation failed: {str(e)}", exc_info=True)
                    await session.rollback()
                    raise

    except Exception as e:
        logger.error(f"Failed to export stores: {str(e)}", exc_info=True)