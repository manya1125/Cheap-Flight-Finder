from data_manager import DataManager 
from datetime import datetime, timedelta
from flight_search import FlightSearch
from notification_manager import NotificationManager
from new_user import NewUser


data_manager = DataManager()
sheet_data = data_manager.get_data()
flight_search = FlightSearch()
new_user = NewUser()

Origin_city = "LON"

print("Welcome to Ozak's Flight Club.\nWe find the best flight deals and email you.")
first_name = input("What is your first name? ")
last_name = input("What is your last_name? ")
email = input("What is your email? ")
if input("Type your email again: ") == email and new_user.is_valid_email(email):
    new_user.register_new_user(first_name, last_name, email)
    print("Thank you for signing up.")
else:
    print("Sorry, that's not the same email.")


if sheet_data[0]["iataCode"] == "":
    for row in sheet_data:
        row["iataCode"] = flight_search.get_code(row["city"])
    data_manager.data = sheet_data
    data_manager.update_data()

tomorrow = datetime.now() + timedelta(days=1)
six_month_from_today = datetime.now() + timedelta(days=(6 * 30))
return_date_initial = tomorrow + timedelta(days=7)
return_date_last = six_month_from_today + timedelta(days=(6 * 30) + 28)

# Try to set up notifications (optional — works without Twilio/Gmail)
try:
    notification_manager = NotificationManager()
    users = data_manager.get_emails()
    users_emails = [row["email"] for row in users]
    notifications_enabled = True
except Exception:
    print("Notifications disabled (Twilio/Gmail not configured). Results will be printed only.")
    notifications_enabled = False

for destination in sheet_data:
    flight = flight_search.search_flights(
        Origin_city,
        destination["iataCode"],
        from_time=tomorrow,
        to_time=six_month_from_today,
        return_to=return_date_last,
        return_from=return_date_initial
    )
    if flight is None:
        continue

    if flight.price < destination["lowestPrice"]:
        if flight.via_airport == "":
            message = (
                f"LOW PRICE ALERT!! Only £{flight.price} to fly from "
                f"{flight.fly_from_city}-{flight.fly_from_airport} to "
                f"{flight.destination_city}-{flight.destination_airport}, "
                f"from {flight.out_date} to {flight.return_date}"
            )
        else:
            message = (
                f"LOW PRICE ALERT!! Only £{flight.price} to fly from "
                f"{flight.fly_from_city}-{flight.fly_from_airport} to "
                f"{flight.destination_city}-{flight.destination_airport}, "
                f"from {flight.out_date} to {flight.return_date}.\n\n"
                f"Flight has 1 stopover, via {flight.via_city}-{flight.via_airport}"
            )

        print(message)

        if notifications_enabled:
            try:
                notification_manager.send_msg(message=message)
                notification_manager.send_emails(users_emails, message)
            except Exception as e:
                print(f"Could not send notification: {e}")