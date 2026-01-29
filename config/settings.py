from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AZURE_SQL_DRIVER: str
    AZURE_SQL_SERVER: str
    AZURE_SQL_DATABASE: str
    AZURE_SQL_USER: str
    AZURE_SQL_PASSWORD: str
    AZURE_CONNECT_TIMEOUT: int = 30

    class Config:
        env_file = ".env"

settings = Settings()
