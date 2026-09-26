from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./coaching_bot.db"
    BALE_BOT_TOKEN: str
    BALE_PAYMENT_TOKEN: str
    # ادمین‌ها — با کاما جدا کن: 123456,789012
    ADMIN_BALE_IDS: str = ""
    # برای سازگاری با قبل
    ADMIN_BALE_ID: str = ""

    @property
    def admin_ids(self) -> List[str]:
        ids = []
        if self.ADMIN_BALE_ID:
            ids.append(str(self.ADMIN_BALE_ID))
        if self.ADMIN_BALE_IDS:
            ids.extend([x.strip() for x in self.ADMIN_BALE_IDS.split(",") if x.strip()])
        return list(set(ids))

    class Config:
        env_file = ".env"

settings = Settings()
