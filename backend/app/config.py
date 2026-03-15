from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://buddy:buddy@localhost:5432/businessbuddy"

    # ── Auth ──────────────────────────────────────────────────────────────
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080   # 7 days

    # ── LLM provider ──────────────────────────────────────────────────────
    # Set LLM_PROVIDER=groq to use Groq instead of Anthropic (free tier available)
    llm_provider: str = "anthropic"          # "anthropic" | "groq"
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    groq_chat_model: str = "llama-3.3-70b-versatile"  # replaces claude-sonnet
    groq_doc_model: str = "llama-3.1-8b-instant"      # replaces claude-haiku

    # ── App ───────────────────────────────────────────────────────────────
    environment: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    frontend_url: str = "http://localhost:5173"

    # ── Documents ─────────────────────────────────────────────────────────
    upload_dir: str = "/tmp/business_buddy_uploads"
    max_upload_mb: int = 50

    # ── Stripe ────────────────────────────────────────────────────────────
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""       # price_xxx for Pro plan
    stripe_price_business: str = ""  # price_xxx for Business plan

    # ── SMTP (for invite emails) ──────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "buddy@yourdomain.com"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key)

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_user)

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
