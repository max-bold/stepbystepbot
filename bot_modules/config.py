from typing import Any, Literal
import json

from bot_modules.runtime import logger


class Settings:
    def __init__(self) -> None:
        self.settings = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            return json.load(open("settings.json", "r", encoding="utf-8"))
        except FileNotFoundError:
            logger.warning(
                "settings.json not found, using default_settings.json without writing"
            )
            return json.load(open("default_settings.json", "r", encoding="utf-8"))

    def reload(self) -> None:
        self.settings = self._load()

    class NSD:
        def __init__(self, data: dict[str, Any]) -> None:
            self.type: Literal["Fixed time", "Period"] = data["type"]
            self.value: int = data["value"]

    @property
    def create_paid_users(self) -> bool:
        if "create_paid_users" not in self.settings:
            logger.warning("Missing settings.create_paid_users; using default: False")
            return False
        return bool(self.settings["create_paid_users"])

    @property
    def next_step_delay(self) -> NSD:
        if "next_step_delay" not in self.settings:
            logger.warning("Missing settings.next_step_delay; using default: Period/300")
            return self.NSD({"type": "Period", "value": 300})
        return self.NSD(self.settings["next_step_delay"])

    def messages(self, key: str) -> str:
        if "messages" not in self.settings:
            logger.warning(f"Missing settings.messages; using default for key: {key}")
            return f"Empty `{key}` message"
        if key not in self.settings["messages"]:
            default_message = f"Empty `{key}` message"
            logger.warning(
                f"Missing settings.messages[{key}]; using default: {default_message}"
            )
            return default_message
        return self.settings["messages"][key]

    @property
    def payment_amount(self) -> int:
        if "payment_amount" not in self.settings:
            logger.warning("Missing settings.payment_amount; using default: 100")
            return 100
        return int(self.settings["payment_amount"])

    @property
    def goods_name(self) -> str:
        if "goods_name" not in self.settings:
            logger.warning("Missing settings.goods_name; using default: 'Доступ к сервису'")
            return "No goods name"
        return str(self.settings["goods_name"])


class Script:
    def __init__(self) -> None:
        self.script = self._load()

    def _load(self) -> list[dict]:
        try:
            return json.load(open("script.json", "r", encoding="utf-8"))
        except FileNotFoundError:
            script = json.load(open("test_script.json", "r", encoding="utf-8"))
            json.dump(script, open("script.json", "w", encoding="utf-8"))
            logger.info("script.json not found, copied test_script.json to script.json")
            return script

    def reload(self) -> None:
        self.script = self._load()

    def __getitem__(self, n):
        return self.script[n]

    def __len__(self):
        return len(self.script)


settings = Settings()
script = Script()
