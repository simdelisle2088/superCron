from asyncio.log import logger
from pathlib import Path
from typing import Dict, List
from sqlalchemy import text
import os
from datetime import datetime
from controller.csv import CSVHandler
from controller.email import EmailConfig, EmailService
from controller.ftp import FTPClient
from controller.stores import Store, get_stores
from settings import PrimarySessionLocal, get_settings, get_primary_db
from dataclasses import dataclass

@dataclass
class InventoryComparison:
    store_id: int
    item_name: str
    db_count: int
    csv_count: int
    difference: int

class InventoryChecker:
    def __init__(self):
        self.settings = get_settings()
        self.stores = get_stores()
        self.ftp_client = FTPClient(
            hostname=self.settings.ftp.hostname,
            username=self.settings.ftp.username,
            password=self.settings.ftp.password,
            port=self.settings.ftp.port
        )

    async def get_db_quantities(self, store: Store) -> Dict[str, int]:
        """Get quantities from database for a store using SQLAlchemy"""
        async with PrimarySessionLocal() as session:
            print(session)
            query = text("""
                SELECT name, count(name) as count 
                FROM locations 
                WHERE name NOT LIKE 'inconnu' 
                AND NOT is_archived 
                AND store = :store_id 
                GROUP BY name 
            """)
            
            result = await session.execute(query, {"store_id": store.id})
            return {row.name: row.count for row in result}

    def get_csv_quantities(self, filename: str) -> Dict[str, int]:
        """Get quantities from CSV file"""
        csv_handler = CSVHandler(filename)
        csv_handler.load()

        quantities = {}
        processed_parts = set()  # Track processed part numbers to avoid duplicates

        for row in csv_handler.data:
            try:
                part_number = row.get('Part Number', '').strip().replace('-', '')
                if not part_number or part_number in processed_parts:
                    continue

                processed_parts.add(part_number)

                # Handle empty or non-numeric values in the Value column
                value_str = row.get('Quantity on Hand', '0').strip()
                if not value_str:
                    qty = 0
                else:
                    try:
                        # Remove any commas and convert to float first
                        cleaned_value = value_str.replace(',', '')
                        qty = int(float(cleaned_value))
                    except ValueError:
                        logger.warning(f"Invalid quantity value '{value_str}' for part {part_number}")
                        qty = 0

                quantities[part_number] = quantities.get(part_number, 0) + qty

            except Exception as e:
                logger.error(f"Error processing row {row}: {str(e)}")
                continue

        return quantities

    def download_store_file(self, store: Store) -> str:
        """Download store's inventory file from FTP"""
        local_filename = f"temp_{store.file['inventaire']}"

        try:
            self.ftp_client.connect()
            logger.info(f"Attempting to download {store.file['inventaire']}")
            self.ftp_client.download_file(store.file['inventaire'], local_filename)
            logger.info(f"Successfully downloaded to {local_filename}")
            return local_filename
        except Exception as e:
            logger.error(f"FTP download error: {str(e)}")
            raise
        finally:
            self.ftp_client.close()

    async def compare_inventory(self, store: Store) -> List[InventoryComparison]:
        """Compare inventory between database and CSV for a store"""
        logger.info(f"Running comparison for store: {store.name}")

        try:
            # Get quantities from database
            db_quantities = await self.get_db_quantities(store)
            logger.info(f"Retrieved {len(db_quantities)} items from database")

            # Download and process CSV file
            local_file = self.download_store_file(store)
            try:
                csv_quantities = self.get_csv_quantities(local_file)
                logger.info(f"Retrieved {len(csv_quantities)} items from CSV")
            finally:
                if os.path.exists(local_file):
                    os.remove(local_file)
            
            # Compare quantities
            all_items = set(db_quantities.keys()) | set(csv_quantities.keys())
            comparisons = []
            
            for item in all_items:
                db_count = db_quantities.get(item, 0)
                csv_count = csv_quantities.get(item, 0)
                difference = csv_count - db_count

                if difference != 0:  # Only track differences
                    comparisons.append(InventoryComparison(
                        store_id=store.id,
                        item_name=item,
                        db_count=db_count,
                        csv_count=csv_count,
                        difference=difference
                    ))

            logger.info(f"Found {len(comparisons)} discrepancies")
            return comparisons

        except Exception as e:
            logger.error(f"Error in compare_inventory for {store.name}: {str(e)}")
            raise

    async def send_notification(self, store: Store, comparisons: List[InventoryComparison]):
        """Send email notification about inventory discrepancies with CSV attachment"""
        if not comparisons:
            logger.info(f"No discrepancies found for store: {store.name}")
            return

        logger.info(f"Preparing notification for {store.recipient} with {len(comparisons)} discrepancies")

        # Create CSV file with discrepancies
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_filename = f"inventory_discrepancies_{store.name}_{timestamp}.csv"

        # Initialize CSV handler with headers
        csv_handler = CSVHandler(
            filename=csv_filename,
            headers=['Item Name', 'Database Count', 'CSV Count', 'Difference']
        )
        
        sorted_comparisons = sorted(comparisons, key=lambda x: x.difference)
        
        # Add sorted comparison data to CSV
        for comp in sorted_comparisons:
            csv_handler.add_row({
                'Item Name': comp.item_name,
                'Database Count': comp.db_count,
                'CSV Count': comp.csv_count,
                'Difference': comp.difference
            })

        # Save the CSV file
        csv_handler.save()

        try:
            # Prepare email content
            subject = f"Rapport des écarts d'inventaire - {store.name}"
            body = f"""
                Nous avons identifié {len(comparisons)} écarts d'inventaire pour {store.name}.
                Veuillez consulter le fichier CSV joint pour plus de détails.
                
                Résumé :
                - Nombre total d'articles avec des écarts : {len(comparisons)}
                - Magasin : {store.name}
                - Généré le : {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                """

            # Initialize email service with config
            email_config = EmailConfig(recipient_email=store.recipient)
            email_service = EmailService(config=email_config)

            # Send email with attachment
            await email_service.send_email_with_attachment(
                subject=subject,
                body=body,
                attachment_path=Path(csv_filename),
                attachment_name=csv_filename
            )

            logger.info(f"Notification sent successfully to {store.recipient}")

        except Exception as e:
            logger.error(f"Failed to send notification for {store.name}: {str(e)}")
            raise
        finally:
            # Clean up the CSV file
            try:
                Path(csv_filename).unlink()
                logger.info(f"Temporary CSV file {csv_filename} cleaned up")
            except Exception as e:
                logger.warning(f"Failed to clean up CSV file {csv_filename}: {str(e)}")

    async def check_all_stores(self):
        """Run inventory check for all stores"""
        logger.info(f"Starting inventory check at {datetime.now()}")

        for store in self.stores:
            try:
                comparisons = await self.compare_inventory(store)
                await self.send_notification(store, comparisons)
            except Exception as e:
                logger.error(f"Error processing store {store.name}: {str(e)}")

        logger.info(f"Completed inventory check at {datetime.now()}")