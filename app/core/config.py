from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str = "YOUR_GOOGLE_CLIENT_ID_HERE"
    GOOGLE_CLIENT_SECRET: str = "YOUR_GOOGLE_CLIENT_SECRET_HERE"
    SECRET_KEY: str = "YOUR_SECRET_KEY_HERE"

    class Config:
        env_file = ".env"

settings = Settings()
