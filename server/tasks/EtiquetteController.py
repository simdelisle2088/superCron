import aiohttp
from pyrate_limiter import Union
import requests
from ftplib import FTP
import pandas as pd
from io import BytesIO
import asyncio
import logging
from typing import Dict, List, Tuple, Optional
from controller.csv import CSVHandler
from settings import get_settings
from dotenv import load_dotenv
import os

# Load the .env file
load_dotenv(
    os.path.join(os.path.dirname(__file__), ".env"),
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
settings = get_settings()

class FTPBusyError(Exception):
    """Custom exception for when FTP server is busy"""
    pass

class SystemBusyError(Exception):
    """Custom exception for when system is busy"""
    pass

class EtiquetteController:
    
    BATCH_SIZE = 1000
    DELAY_BETWEEN_BATCHES = 1

    FILES_CONFIG = {
        "PRIXETIQUETTECHATEAUGUAY.csv": {
            "store_id": "0003"
        },
        "PRIXETIQUETTEST-HUBERT.csv": {
            "store_id": "0001"
        },
        "PRIXETIQUETTEST-JEAN.csv": {
            "store_id": "0002"
        }
    }

    def __init__(self, include_price: bool = True):
        """ Initialize the controller with a flag to determine whether to include price information """
        self.include_price = include_price
        # Define the key mappings based on whether price is included
        self._key_mapping = {
            'Part Number': 'pi',
            'Part Description': 'pn', 
            'Value': 'kc',
            'UPC Code': 'pc'
        }
        if self.include_price:
            self._key_mapping['Price'] = 'pp'

    def convert_keys(self, data_list: List[Dict]) -> List[Dict]:
        """ Convert dictionary keys based on the configured mapping """
        return [{self._key_mapping[k]: v for k, v in item.items() 
                if k in self._key_mapping} for item in data_list]

    @staticmethod
    def clean_data(array: List[Dict]) -> List[Dict]:
        """ Clean the data by handling NaN values """
        for item in array:
            for key, value in item.items():
                if pd.isna(value):
                    item[key] = 0
        return array
    
    # @staticmethod
    # def clean_data(array: List[Dict]) -> List[Dict]:
    #     """ Clean the data by handling NaN values and filtering UPC codes """
    #     cleaned_array = []
    #     for item in array:
    #         # First handle NaN values
    #         for key, value in item.items():
    #             if pd.isna(value):
    #                 item[key] = 0

    #         # Check if UPC Code contains only digits
    #         upc = str(item.get('UPC Code', ''))
    #         if upc.isdigit():
    #             cleaned_array.append(item)
    #         else:
    #             logger.info(f"Removing item with invalid UPC Code: {item}")
    #     return cleaned_array

    @staticmethod
    def merge_price_data(prices: List[Dict], data: List[Dict]) -> List[Dict]:
        """ Merge price information with the original data while preserving duplicate Part Numbers """
        # Group data by Part Number to preserve all entries
        merged_data = []

        # Create a dictionary from prices for faster lookup
        price_dict = {item['Part Number']: item for item in prices}

        # Iterate through each item in original data
        for item in data:
            part_num = item['Part Number']
            new_item = item.copy()  # Create a copy of the original item

            # If we have price info for this part number, update the item
            if part_num in price_dict:
                # Update with price data, excluding Part Number to avoid overwrite
                price_info = {k: v for k, v in price_dict[part_num].items() if k != 'Part Number'}
                new_item.update(price_info)

            merged_data.append(new_item)
    
        return merged_data
    
    @staticmethod
    def get_processed_parts_prices(parts: List[Dict]) -> Tuple[List[Dict], bool]:
        """ Query and process parts pricing from API """
        try:
            # Create parts list with validation
            parts_list = []
            for part in parts:
                part_number = str(part.get('Part Number', '')).strip()
                if ' ' in part_number:  # Ensure there's a space separator
                    code, number = part_number.split(' ', 1)
                    parts_list.append({"Code": code, "PartNum": number})

            if not parts_list:
                logger.warning("No valid parts found to process")
                return [], False
            # Make API request
            response = requests.post(
                settings.esl.apiurl+"/getPrices",
                headers={'Content-Type': 'application/json'},
                json={'priceParams': parts_list},
                timeout=60
            )
            response.raise_for_status()

            # Validate response
            response_data = response.json()
            if not isinstance(response_data, dict):
                raise ValueError(f"Expected dictionary response, got {type(response_data)}")

            result = response_data.get('result')
            if not isinstance(result, dict):
                raise ValueError(f"Expected dictionary result, got {type(result)}")

            # Process results
            processed_parts = []
            for parts_group in result.values():
                if not isinstance(parts_group, list):
                    continue
                for info in parts_group:
                    if not isinstance(info, dict):
                        continue
                    try:
                        processed_parts.append({
                            'Part Number': f"{info['MfgCode']} {info['PartNum']}", 
                            'Price': info['Price']['UnitCost']
                        })
                    except (KeyError, TypeError) as e:
                        logger.warning(f"Skipping malformed part info: {e}")
                        continue

            return processed_parts, True

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return [], False
        except Exception as e:
            logger.error(f"Error processing parts: {e}")
            return [], False
    
    async def process_csv_with_retry(
            self,
            ftp: FTP, 
            file_name: str, 
            max_retries: int = 3, 
            initial_delay: int = 5
        ) -> Tuple[Optional[List[Dict]], bool]:
            """ Process a single CSV file with retry logic """
            delay = initial_delay
            
            for attempt in range(max_retries):
                try:
                    with BytesIO() as bio:
                        # Download the file content to BytesIO
                        ftp.retrbinary(f"RETR /{file_name}", bio.write)
                        bio.seek(0)
                        
                        # Convert BytesIO content to string
                        csv_content = bio.getvalue().decode('utf-8')
                        
                        # Create a temporary file to store the CSV content
                        temp_filename = f"temp_{file_name}"
                        with open(temp_filename, 'w', encoding='utf-8') as temp_file:
                            temp_file.write(csv_content)
                        
                        try:
                            # Use CSVHandler to read the file
                            csv_handler = CSVHandler(temp_filename)
                            csv_handler.load()
                            
                            if not csv_handler.data:
                                logger.error(f"Empty data for {file_name}")
                                return None, False
                                
                            return csv_handler.data, True
                            
                        finally:
                            # Clean up temporary file
                            if os.path.exists(temp_filename):
                                os.remove(temp_filename)
                        
                except Exception as e:
                    if "busy" in str(e).lower():
                        logger.warning(f"FTP server busy on attempt {attempt + 1}, waiting {delay} seconds...")
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue
                        
                    logger.error(f"Error processing {file_name} on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue
                        
                    return None, False
            
            return None, False


    @staticmethod
    def batch_parts_list(parts: List[Dict], batch_size: int = 1000) -> List[List[Dict]]:
        """ Split parts list into batches """ 
        return [parts[i:i + batch_size] for i in range(0, len(parts), batch_size)]

    async def process_batch(self, batch: List[Dict]) -> Tuple[List[Dict], bool]:
        """ Process a batch of data, optionally including price information """ 
        if not self.include_price:
            return self.clean_data(batch), True

        # If including price, get and merge price information
        prices, success = self.get_processed_parts_prices(batch)
        if not success:
            return [], False

        cleaned_data = self.merge_price_data(prices, batch)
        return self.clean_data(cleaned_data), True

    async def post_data_with_retry(
        self,
        session_data: Union[List[Dict], Dict],
        store_id: str,
        max_retries: int = 3,
        initial_delay: int = 5
    ) -> bool:
        """ Post processed data to the API with retry logic """ 
        delay = initial_delay
        if isinstance(session_data, dict):
            data_to_process = [session_data]
        else:
            data_to_process = session_data
    
        batches = self.batch_parts_list(data_to_process, self.BATCH_SIZE)
        logger.info(f"Processing {len(batches)} batches of up to {self.BATCH_SIZE} items each")
    
        overall_success = True

        for i, batch in enumerate(batches, 1):
            logger.info(f"Processing batch {i} of {len(batches)} ({len(batch)} items)")
            
            processed_data, success = await self.process_batch(batch)
            if not success:
                overall_success = False
                continue
            products = self.convert_keys(processed_data)
            
            if not products:
                logger.error(f"No valid products in batch {i}")
                overall_success = False
                continue

            payload = {
                "store_code": store_id,
                "f1": products,
                "is_base64": "0", 
                "f2": "40:d6:3c:5e:11:63",
                "sign": settings.esl.sign
            }

            success = await self._send_batch_to_api(payload, i, max_retries, delay)
            if not success:
                logger.info(f"Failed to store data to ESL. retrying in {delay}s")
                asyncio.sleep(delay)
                success = await self._send_batch_to_api(payload, i, max_retries, delay)
                if not success:
                    logger.error(f"Failed to store data to ESL {payload}")
                    overall_success = False


            await asyncio.sleep(self.DELAY_BETWEEN_BATCHES)

        return overall_success

    async def _send_batch_to_api(
        self,
        payload: Dict,
        batch_num: int,
        max_retries: int,
        initial_delay: int
    ) -> bool:
        """ Send a batch of data to the API with retry logic """ 
        delay = initial_delay
        
        async with aiohttp.ClientSession() as session:
            for attempt in range(max_retries):
                try:
                    async with session.post(
                        'https://esl.pasuper.xyz/api/default/product/create_multiple',
                        headers={'Content-Type': 'application/json'},
                        json=payload,
                        timeout=30
                    ) as response:
                        result = await response.json()
                        if response.status == 200 and isinstance(result, dict) and result.get('error_code') == 0:
                            return True
                        
                        logger.error(f"API error in batch {batch_num}: Status {response.status}, Response: {result}")
                
                except Exception as e:
                    logger.error(f"API error on attempt {attempt + 1} for batch {batch_num}: {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                
        return False

    async def read_and_store_files(self):
        """ Read files from FTP and store their contents """
        ftp = None
        try:
            ftp = FTP(settings.esl.hostname)
            ftp.login(settings.esl.username, settings.esl.password)

            files_on_ftp = ftp.nlst("/")
            logger.info(f"Available files in FTP root: {files_on_ftp}")

            errors = []
            for file_name, config in self.FILES_CONFIG.items():
                logger.info(f"Processing {file_name} for store {config['store_id']}")
                
                data, success = await self.process_csv_with_retry(ftp, file_name)
                if not success:
                    errors.append(f"Failed to process {file_name}")
                    continue

                store_success = await self.post_data_with_retry(
                    session_data=data,
                    store_id=config['store_id']
                )
                
                if not store_success:
                    errors.append(f"Failed to store some data for {file_name}")

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            errors.append(str(e))
            
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception as e:
                    logger.error(f"Error closing FTP connection: {e}")

        if errors:
            raise Exception(f"Errors occurred: {'; '.join(errors)}")

async def etiquette_scheduled_job(include_price: bool = True):
    """  Scheduled job that can handle both price and quantity updates """ 
    try:
        controller = EtiquetteController(include_price=include_price)
        await controller.read_and_store_files()
        job_type = "price and quantity" if include_price else "quantity"
        logger.info(f"Completed {job_type} update job successfully")
    except Exception as e:
        logger.error(f"Error in scheduled job test: {e}")
        raise


# You can now use these functions like this:
async def price_label_scheduled_job():
    """ Job that includes price updates """ 
    await etiquette_scheduled_job(include_price=True)

async def qty_label_scheduled_job():
    """ Job that only updates quantity information """ 
    await etiquette_scheduled_job(include_price=False)