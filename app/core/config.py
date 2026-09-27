from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "EVE Healthcare Diagnostic Booking & Payment Service"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/eve_healthcare"

    # JWT Authentication
    JWT_SECRET_KEY: str = "eve-insecure-dev-secret-key-change-in-production-32bytes-min"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours for convenience in demo

    # Webhook Security
    WEBHOOK_SECRET: str = "eve-webhook-dev-secret-key-simulated-provider-signature"

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["*"]

    # Development Seeds
    SEED_ADMIN_EMAIL: str = "admin@evehealth.com"
    SEED_ADMIN_PASSWORD: str = "AdminSecret123!"
    SEED_ADMIN_NAME: str = "System Administrator"

    SEED_PATIENT_EMAIL: str = "patient@evehealth.com"
    SEED_PATIENT_PASSWORD: str = "PatientSecret123!"
    SEED_PATIENT_NAME: str = "Jane Doe"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
