import uuid
from dotenv import load_dotenv
from os import getenv

load_dotenv()

from yookassa import Configuration, Payment

store_id = getenv("STORE_ID")
api_key = getenv("YKASSA_API_KEY")
bot_link = getenv("BOT_LINK")

if not store_id:
    raise ValueError("STORE_ID environment variable not set")
if not api_key:
    raise ValueError("YKASSA_API_KEY environment variable not set")
if not bot_link:
    raise ValueError("BOT_LINK environment variable not set")

Configuration.account_id = store_id
Configuration.secret_key = api_key


def create_payment(
    amount_rub: int,
    item_name: str = "Доступ к сервису",
    email: str = "user@example.com",
) -> tuple[str, str]:
    amount_value = f"{amount_rub:.2f}"
    payment = Payment.create(
        {
            "amount": {"value": amount_value, "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": bot_link,
            },
            "capture": True,
            "description": "Оплата заказа в StepByStepBot",
            "receipt": {
                "customer": {"email": email},
                "items": [
                    {
                        "description": item_name,
                        "quantity": 1.000,
                        "amount": {"value": amount_value, "currency": "RUB"},
                        "vat_code": 1,
                        "payment_mode": "full_prepayment",
                        "payment_subject": "intellectual_activity",
                    }
                ],
            },
        },
        uuid.uuid4(),
    )
    return str(payment.id), (
        payment.confirmation.confirmation_url if payment.confirmation else ""
    )


def get_payment_status(payment_id: str) -> str | None:
    payment = Payment.find_one(payment_id)
    if payment is None:
        return None
    else:
        return payment.status
