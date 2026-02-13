import json


try:
    promo_codes: list[str] = json.load(open("promo_codes.json", "r", encoding="utf-8"))
except FileNotFoundError:
    promo_codes: list[str] = []


def save_promo_codes() -> None:
    json.dump(promo_codes, open("promo_codes.json", "w", encoding="utf-8"))
