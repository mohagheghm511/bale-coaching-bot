from bale import Bot

_bot: Bot = None

def init_bot(token: str) -> Bot:
    global _bot
    _bot = Bot(token=token)
    return _bot

def get_bot() -> Bot:
    if _bot is None:
        raise RuntimeError("Bot has not been initialized. Call init_bot() first.")
    return _bot
