from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from tasks.RapportDiffInv import InventoryChecker
from tasks.UpdateUnknownInv import LocationUpdateService
from tasks.EtiquetteController import price_label_scheduled_job, qty_label_scheduled_job
from tasks.OfflineInv import export_store

def setup_scheduler(app):
    scheduler = AsyncIOScheduler()
    
    # Create instances for classes
    location_service = LocationUpdateService()
    inventory_checker = InventoryChecker()


    scheduler.add_job(
        # Run once daily at 20:00 (8 PM)
        price_label_scheduled_job,
        trigger=CronTrigger(minute="0", hour="20"), 
        id="tag_prices",
        name="Tag Prices",
        replace_existing=True
    )

    scheduler.add_job(
        # Run once daily at 21:00 (9 PM)
        location_service.update_unknown_locations,  # Use instance method
        trigger=CronTrigger(minute="0", hour="21"),
        id="update_and_get_unknown_locations",
        name="Update and Get Unknown Locations",
        replace_existing=True
    )

    scheduler.add_job(
        # Run once daily at 1:20 AM
        inventory_checker.check_all_stores,
        trigger=CronTrigger(minute="20", hour="1"),
        id="inventory_diff",
        name="Inventory Difference",
        replace_existing=True
    )

    scheduler.add_job(
        # Run every 30 minutes from 7 AM to 7 PM
        qty_label_scheduled_job,
        trigger=CronTrigger(minute="*/30", hour="7-19"), 
        id="tag_quantities",
        name="Tag Quantities",
        replace_existing=True
    )

    scheduler.add_job(
        # Run every 15 minutes from 7 AM to 7 PM
        export_store,
        trigger=CronTrigger(minute='*/15', hour='7-19'),
        id=f'store_export',
        name=f'Export locations for store',
        replace_existing=True
    )

    # Store scheduler instance in app state
    app.state.scheduler = scheduler

    # Start the scheduler
    scheduler.start()

    @app.on_event("shutdown")
    async def shutdown_scheduler():
        scheduler.shutdown()