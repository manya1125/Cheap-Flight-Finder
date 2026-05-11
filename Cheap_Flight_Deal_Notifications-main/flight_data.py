class FlightData:
    def __init__(self,price,fly_from_city,fly_from_airport,destination_city,destination_airport,out_date,return_date,via_city="",via_airport=""):
        self.price = price
        self.fly_from_city = fly_from_city
        self.fly_from_airport = fly_from_airport
        self.destination_city = destination_city
        self.destination_airport = destination_airport
        self.out_date = out_date
        self.return_date = return_date
        self.via_city = via_city
        self.via_airport = via_airport