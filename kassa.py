from time import sleep
import uuid
from dotenv import load_dotenv
from os import getenv

load_dotenv()

from yookassa import Configuration, Payment

Configuration.account_id = getenv("STORE_ID")
Configuration.secret_key = getenv("YKASSA_API_KEY")
bot_link = getenv("BOT_LINK")


def create_payment() -> tuple[str, str]:
    payment = Payment.create(
        {
            "amount": {"value": "100.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": bot_link,
            },
            "capture": True,
            "description": "Оплата заказа в StepByStepBot",
        },
        uuid.uuid4(),
    )
    return payment.id, payment.confirmation.confirmation_url


def get_payment_status(payment_id: str) -> str | None:
    payment = Payment.find_one(payment_id)
    if payment is None:
        return None
    else:
        return payment.status
