from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.declarative import declarative_base
from functools import lru_cache
from enum import Enum
import os
from dotenv import load_dotenv

# Load environment variables first
env = os.getenv("APP_ENV", "local")
env_file = f".env"
print('EVN', env)
if (env == "local"): env_file = f".env.local"
load_dotenv(env_file, override=True)

# Define EnvironmentType before using it
class EnvironmentType(str, Enum):
    LOCAL = "local"
    DEVELOPMENT = "development"
    PRODUCTION = "production"

class NASSettings(BaseSettings):
    hostname: str = os.getenv('NAS_HOSTNAME', '')
    username: str = os.getenv('NAS_USERNAME', '')
    password: str = os.getenv('NAS_PASSWORD', '')
    port: int = int(os.getenv('NAS_PORT', ''))

    model_config = SettingsConfigDict(
        env_prefix="NAS_",
        case_sensitive=True,
        extra="allow"
    )

class FTPESLSettings(BaseSettings):
    hostname: str = os.getenv('FTP_ESL_HOSTNAME', '')
    username: str = os.getenv('FTP_ESL_USERNAME', '')
    password: str = os.getenv('FTP_ESL_PASSWORD', '')
    port: int = int(os.getenv('FTP_ESL_PORT', ''))
    apiurl: str = os.getenv('API_STRAPI', "http://localhost:8080")
    sign: str = os.getenv("ESL_SIGN", '80805d794841f1b4') 

    model_config = SettingsConfigDict(
        env_prefix="FTP_ESL_",
        case_sensitive=True,
        extra="allow"
    )
class FTPSettings(BaseSettings):
    hostname: str = os.getenv('FTP_HOSTNAME', "docker.gamcar.ca")
    username: str = os.getenv('FTP_USERNAME', "ftp-user")
    password: str = os.getenv('FTP_PASSWORD', "Pasuper7803!")
    port: int = int(os.getenv('FTP_PORT', 21))

    model_config = SettingsConfigDict(
        env_prefix="FTP_",
        case_sensitive=True,
        extra="allow"
    )

class APISettings(BaseSettings):
    version: str = "v1"
    prefix: str = "/api/v1"
    API_STRAPI: str = os.getenv('API_STRAPI', "")

    esl_sign: str = "80805d794841f1b4"

    model_config = SettingsConfigDict(
        env_prefix="API_",
        case_sensitive=True,
        extra="allow"
    )

class DatabaseSettings(BaseSettings):
    port: int = int(os.getenv('DB_PORT', 3306))
    user_primary: str = os.getenv('DB_USER_PRIMARY', '')
    password_primary: str = os.getenv('DB_PASSWORD_PRIMARY', '')
    database_primary: str = os.getenv('DB_DATABASE_PRIMARY', '')
    user_secondary: str = os.getenv('DB_USER_SECONDARY', '')
    password_secondary: str = os.getenv('DB_PASSWORD_SECONDARY', '')
    database_secondary: str = os.getenv('DB_DATABASE_SECONDARY', '')
    host: str = os.getenv('DB_HOST', 'localhost')
    recipient: str = os.getenv('DEFAULT_RECIPIENT', '')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def primary_url(self) -> str:
        url = f"mysql+aiomysql://{self.user_primary}:{self.password_primary}@{self.host}:{self.port}/{self.database_primary}"
        return url
    
    @property
    def secondary_url(self) -> str:
        url = f"mysql+aiomysql://{self.user_secondary}:{self.password_secondary}@{self.host}:{self.port}/{self.database_secondary}"
        return url

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=True,
        extra="allow"
    )

class Settings(BaseSettings):
    app_env: EnvironmentType = EnvironmentType(os.getenv('APP_ENV', 'local'))
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    db: DatabaseSettings = DatabaseSettings()
    api: APISettings = APISettings()
    nas: NASSettings = NASSettings()
    esl: FTPESLSettings = FTPESLSettings()
    ftp: FTPSettings = FTPSettings()

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file_encoding='utf-8',
        extra="allow",
        env_nested_delimiter='__'
    )
@lru_cache()
def get_settings() -> Settings:
    """Get settings instance with environment-based configuration"""
    env = os.getenv("APP_ENV", "local")
    env_file = f".env"
    if (env == "local"): env_file = f".env.local"
    
    print(f"Attempting to load settings from {env_file}")
    print(f"File exists: {os.path.exists(env_file)}") 
    
    try:
        settings = Settings(_env_file=env_file)
        print(f"Settings loaded successfully")
        return settings
    except Exception as e:
        print(f"Error loading settings from {env_file}: {str(e)}")
        return Settings()

# Create settings instance
settings = get_settings()

# Create a base class for your models
Base = declarative_base()

# Create the engines using the settings instance
primary_engine = create_async_engine(
    settings.db.primary_url,
    pool_size=8,
    pool_recycle=21600,
    echo=False,
)

secondary_engine = create_async_engine(
    settings.db.secondary_url,
    pool_size=2,
    pool_recycle=21600,
    echo=False,
)

# Create a session factory function for the primary database
def PrimarySessionLocal():
    return AsyncSession(
        bind=primary_engine,
        expire_on_commit=False,
    )


# Create a session factory function for the secondary database
def SecondarySessionLocal():
    return AsyncSession(
        bind=secondary_engine,
        expire_on_commit=False,
    )

# Session factories
async def get_primary_db() -> AsyncSession:
    async with PrimarySessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_secondary_db() -> AsyncSession:
    async with SecondarySessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

