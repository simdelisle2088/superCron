import logging

from fastapi import Depends, FastAPI
from scheduler import setup_scheduler
from tasks.EtiquetteController import price_label_scheduled_job, qty_label_scheduled_job
from tasks.OfflineInv import export_store
from tasks.RapportDiffInv import InventoryChecker
from tasks.UpdateUnknownInv import LocationUpdateService
from settings import EnvironmentType, get_settings, Settings

settings = get_settings()

# Log the app start and print the state of deployment
logging.warning(
    f"|- ({settings.app_env}) ============================================== ({settings.app_env}) -|"
)
logging.warning(
    f"|- ({settings.app_env}) |-------- NOTICE: Api is now running --------| ({settings.app_env}) -|"
)
logging.warning(
    f"|- ({settings.app_env}) ============================================== ({settings.app_env}) -|"
)

app = FastAPI(
    title="SuperCron",
    debug=settings.debug
)
if (settings.app_env == EnvironmentType.PRODUCTION):
    setup_scheduler(app)

@app.get("/")
async def root():
    return {"message": "API is running"}

@app.get("/health")
async def health_check(settings: Settings = Depends(get_settings)):
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "api_version": settings.api.version,
        "db_settings": {
            "port": settings.db.port,
            "primary_db": settings.db.database_primary,
            "secondary_db": settings.db.database_secondary
        }
    }

@app.get("/manual/update_price_label")
async def manual_update_prixetiquette():
    try:
        logging.warning('Manually Called "update_price_label"')
        await price_label_scheduled_job()
        return {"message": "Data updated successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/manual/update_qty_label")
async def manual_update_prixetiquette():
    try:
        logging.warning('Manually Called "update_qty_label"')
        await qty_label_scheduled_job()
        return {"message": "Data updated successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/manual/offline_inv")
async def offline_inv_endpoint():
    try:
        logging.warning('Manually Called "offline_inv"')
        await export_store()
        return {"message": "Data updated successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/manual/unknown_inv")
async def unknown_inv_endpoint():
    try:
        logging.warning('Manually Called "unknown_inv"')
        service = LocationUpdateService()
        await service.update_unknown_locations()
        return {"message": "Data updated successfully"}
    except Exception as e:
        return {"error": str(e)}
    

@app.get("/manual/diff_inv")
async def diff_inv_endpoint():
    try:
        logging.warning('Manually Called "diff_inv"')
        service = InventoryChecker()
        await service.check_all_stores()
        return {"message": "Data updated successfully"}
    except Exception as e:
        return {"error": str(e)}
