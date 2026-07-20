from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./b2b_vpn.db"
    JWT_SECRET: str = "super_secret_jwt_key_b2b_vpn_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    AMNEZIA_API_URL: str = "http://localhost:8082"
    AMNEZIA_ADMIN_EMAIL: str = "admin@amnez.ia"
    AMNEZIA_ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"

settings = Settings()
