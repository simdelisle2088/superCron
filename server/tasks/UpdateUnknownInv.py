import logging
from typing import List, Tuple, Optional
from pathlib import Path
import csv
from datetime import datetime
from sqlalchemy import (
    func, select, and_, distinct, update, Column, Integer, String, 
    Boolean, TIMESTAMP, SMALLINT, text
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import case as case_
from controller.email import EmailConfig, EmailService
from settings import PrimarySessionLocal
from controller.stores import Store, get_stores


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create SQLAlchemy Base
Base = declarative_base()
stores = get_stores()

# SQLAlchemy Models
class Location(Base):
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    upc = Column(String(45))
    name = Column(String(128))
    store = Column(String(45))
    level = Column(String(45))
    row = Column(String(45))
    side = Column(String(45))
    column = Column(String(45))
    shelf = Column(String(45))
    bin = Column(String(45))
    full_location = Column(String(45))
    updated_by = Column(String(45))
    updated_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
    created_by = Column(String(45))
    created_at = Column(TIMESTAMP, server_default=text('CURRENT_TIMESTAMP'))
    is_archived = Column(SMALLINT, default=0)

class Inventory(Base):
    __tablename__ = 'inventory'

    id = Column(Integer, primary_key=True)
    upc = Column(String)
    sku = Column(String)
    item = Column(String)
    description = Column(String)
    pack = Column(Integer)

class LocationUpdateService:
    def __init__(self):
        self.email_service = EmailService(EmailConfig(recipient_email=stores[0].recipient))
        
    async def update_unknown_locations(self) -> None:
        """
        Main function to update unknown locations and send email report
        """
        try:
            async with PrimarySessionLocal() as session:
                # Get UPCs and items from inventory for unknown locations
                updated_count = await self._update_locations_from_inventory(session)
                logger.info(f"Updated {updated_count} locations with inventory items")
                
                # Get remaining unknown locations
                remaining_locations = await self._get_remaining_unknown_locations(session)
                logger.info(f"Found {len(remaining_locations)} remaining unknown locations")
                
                # Generate and send report
                if remaining_locations:
                    await self._send_unknown_locations_report(remaining_locations)
                    
        except Exception as e:
            logger.error(f"Error in update_unknown_locations: {str(e)}")
            raise

    async def _update_locations_from_inventory(self, session: AsyncSession) -> int:
        try:
            # Get all distinct UPCs with 'inconnu' name
            upc_query = select(distinct(Location.upc)).where(
                and_(
                    Location.name == 'inconnu',
                    Location.is_archived == 0
                )
            )
            result = await session.execute(upc_query)
            upcs = [row[0] for row in result]
            logger.info(upcs)
            if not upcs:
                return 0

            # Get matching inventory items
            inventory_query = select(Inventory.upc, Inventory.item).where(
                Inventory.upc.in_(upcs)
            )
            result = await session.execute(inventory_query)
            upc_to_item = {row.upc: row.item for row in result}

            total_updated = 0
            for upc, item in upc_to_item.items():
                update_stmt = (
                    update(Location)
                    .where(
                        and_(
                            Location.upc == upc,
                            Location.name == 'inconnu',
                            Location.is_archived == 0
                        )
                    )
                    .values(
                        name=item,
                        updated_at=datetime.now(),
                        updated_by='system'
                    )
                )
                result = await session.execute(update_stmt)
                total_updated += result.rowcount
                await session.commit()

            return total_updated

        except Exception as e:
            logger.error(f"Error in _update_locations_from_inventory: {str(e)}")
            await session.rollback()
            raise

    async def _get_remaining_unknown_locations(self, session: AsyncSession) -> List[Tuple[str, str, str]]:
        """
        Get distinct UPCs with all their possible locations combined into a single row.
        Returns a list of dictionaries containing UPC and concatenated location information.
        """
        try:
            # Create a subquery to get distinct combinations of location fields for each UPC
            # Use full_location field which already contains the complete location
            location_concat = func.group_concat(
                Location.full_location
            ).label('locations')
            
            # Main query
            query = (
                select(
                    Location.upc,
                    location_concat
                )
                .where(and_(
                    Location.name == 'inconnu',
                    Location.is_archived == 0
                )            )
                .group_by(Location.upc)
                .order_by(Location.full_location)
            )
            
            result = await session.execute(query)
            rows = result.all()
            
            # Format the results
            # Format results as list of tuples (upc, name, locations)
            return [(row.upc, 'inconnu', row.locations) for row in rows]
            
        except Exception as e:
            logger.error(f"Error in get_distinct_upc_locations: {str(e)}")
            raise


    async def _send_unknown_locations_report(
        self,
        locations: List[Tuple[str, str, str]]
    ) -> None:
        """
        Generate CSV report and send via email
        """
        try:
            # Generate CSV file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = Path(f"unknown_locations_{timestamp}.csv")
            
            with open(filepath, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['UPC', 'Location Name', 'Full Location'])
                writer.writerows(locations)

            # Send email
            subject = "Rapport emplacements des inconnus"
            body = f"""
            Vous trouverez ci-joint le rapport des inconnus restants.
            Nombre total d'inconnus : {len(locations)}
            """

            await self.email_service.send_email_with_attachment(
                subject=subject,
                body=body,
                attachment_path=filepath
            )

            # Clean up the file
            filepath.unlink()
            
        except Exception as e:
            logger.error(f"Error in _send_unknown_locations_report: {str(e)}")
            raise

# Usage example
async def main():
    service = LocationUpdateService()
    await service.update_unknown_locations()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())