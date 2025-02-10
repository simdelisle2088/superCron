from dataclasses import dataclass
from typing import Dict
from settings import EnvironmentType, get_settings

@dataclass
class Store:
    id: int
    name: str
    recipient: str
    file: Dict[str, str]  # Added file attribute to store files mapping

def get_stores():
    settings = get_settings()

    stores = [
        Store(
            id=1,
            name='St-Hubert',
            recipient='jonathan.carriere@pasuper.com',
            file={
                'etiquettes': 'PRIXETIQUETTEST-HUBERT.csv',
                'inventaire': 'SUPERPICKERSTHUBERT.csv',
            }
        ),
        # Store(
        #     id=2,
        #     name='St-Jean',
        #     recipient='alexandre.poirier@pasuper.com',
        #     file={
        #         'etiquettes': 'PRIXETIQUETTEST-JEAN.csv',
        #     }
        # ),
        # Store(
        #     id=3,
        #     name='Chateauguay',
        #     recipient='james.ross@pasuper.com',
        #     file={
        #         'etiquettes': 'PRIXETIQUETTECHATEAUGUAY.csv',
        #     }
        # ),
    ]
    
    if settings.app_env == EnvironmentType.LOCAL:
        for store in stores:
            store.recipient = settings.db.recipient
            
    return stores