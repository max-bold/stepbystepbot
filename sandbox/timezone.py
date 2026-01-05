

#print current time in timezone UTC+3
from datetime import datetime, timezone, timedelta
# Get current time in UTC+3
utc_plus_3 = timezone(timedelta(hours=3))
now = datetime.now(utc_plus_3)
start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
hours_elapsed = (now - start_of_day).total_seconds() / 3600

print(f"Current time in UTC+3: {now.isoformat()}")
print(f"Start of day in UTC+3: {start_of_day.isoformat()}")
print(f"Hours from start of day: {hours_elapsed:.2f}")