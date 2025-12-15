from typing import Optional

from pydantic_settings import BaseSettings
from pydantic import AnyUrl, SecretStr


class Settings(BaseSettings):
    # OpenAI
    OPENAI_API_KEY: SecretStr
    OPENAI_EMBEDDING_MODEL: str

    # Qdrant (Cloud)
    QDRANT_URL: Optional[AnyUrl] = None
    QDRANT_API_KEY: Optional[SecretStr] = None

    # Qdrant (Local Mode)
    # 例: QDRANT_PATH=.qdrant または QDRANT_PATH=:memory:
    QDRANT_PATH: Optional[str] = None

    # 共通
    QDRANT_COLLECTION: str = "who_diabetes_guideline"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def qdrant_mode(self) -> str:
        """cloud / local を判定"""
        if self.QDRANT_URL is not None:
            return "cloud"
        if self.QDRANT_PATH is not None:
            return "local"
        raise ValueError("Set either QDRANT_URL (cloud) or QDRANT_PATH (local).")


settings = Settings()
