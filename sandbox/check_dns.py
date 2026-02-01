import dns.resolver
from time import sleep

while True:
    # Check DNS records for kuhnerking.ru
    try:
        answers = dns.resolver.resolve('kuhnerking.ru', 'TXT')
        for rdata in answers:
            print(f'kuhnerking.ru TXT record: {rdata.strings}')
    except Exception as e:
        print(f'Error retrieving TXT records for kuhnerking.ru: {e}')
    print('---')
    sleep(10)