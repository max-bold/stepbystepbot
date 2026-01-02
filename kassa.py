from time import sleep
import uuid
from dotenv import load_dotenv
from os import getenv

load_dotenv()

from yookassa import Configuration, Payment

Configuration.account_id = getenv("STORE_ID")
Configuration.secret_key = getenv("YKASSA_API_KEY")


def create_payment() -> tuple[str, str]:
    payment = Payment.create(
        {
            "amount": {"value": "100.00", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": "https://www.example.com/return_url",
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


# if payment.confirmation:
#     print(payment.confirmation.confirmation_url)  # For debugging purposes

# while payment.status != "succeeded":
#     payment = Payment.find_one(payment.id)
#     print(f"Payment status: {payment.status}")
#     sleep(1)

# if payment.metadata:
#     print(f"Payment from {payment.metadata['id']} succeeded!")

if __name__ == "__main__":
    payment_id, confirmation_url = create_payment()
    print(f"Created payment with ID: {payment_id}")
    print(f"Confirmation URL: {confirmation_url}")
    sleep(5)  # Simulate waiting for user to complete payment
    status = get_payment_status(payment_id)
    print(f"Payment status: {status}")
