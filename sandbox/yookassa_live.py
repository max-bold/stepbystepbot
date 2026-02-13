# Add D:\Code\stepbystepbot\kassa.py to sys.path
import sys
sys.path.append(r'D:\Code\stepbystepbot')
import kassa

kassa.Configuration.account_id = "1270390"
kassa.Configuration.secret_key = "live_tdOApZvHUNYOX9a7w2MXHwNYEmidxFgLF5PjXHo8gwQ"

if __name__ == "__main__":
    id, url = kassa.create_payment(10, "Тестовая покупка")
    print(f"Payment ID: {id}, Confirmation URL: {url}")