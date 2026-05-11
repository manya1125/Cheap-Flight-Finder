import os

import requests

from flight_data import FlightData

API_KEY = os.getenv("KIWI_API_KEY", "")
END_POINT = "https://api.tequila.kiwi.com"
REQUEST_TIMEOUT = 20


class FlightSearch:
    def __init__(self):
        self.api_key = API_KEY

    def is_configured(self):
        return bool(self.api_key)

    def _headers(self):
        if not self.api_key:
            return None
        return {"apikey": self.api_key}

    def get_code(self, city_name):
        headers = self._headers()
        if not headers:
            return ""

        location_endpoint = f"{END_POINT}/locations/query"
        parameters = {
            "term": city_name,
            "locale": "en-US",
            "location_types": "airport",
        }

        try:
            response = requests.get(
                url=location_endpoint,
                params=parameters,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            locations = response.json().get("locations", [])
            return locations[0]["id"] if locations else ""
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return ""

    def search_flights(self, origin_city_code, destination_airport, from_time, to_time, return_from, return_to):
        headers = self._headers()
        if not headers or not destination_airport:
            return None

        parameters = {
            "fly_from": origin_city_code,
            "fly_to": destination_airport,
            "date_from": from_time.strftime("%d/%m/%Y"),
            "date_to": to_time.strftime("%d/%m/%Y"),
            "return_to": return_to.strftime("%d/%m/%Y"),
            "return_from": return_from.strftime("%d/%m/%Y"),
            "nights_in_dst_from": 7,
            "nights_in_dst_to": 28,
            "max_stopovers": 0,
            "curr": "INR",
        }

        direct_result = self._search(parameters, headers)
        if direct_result:
            return direct_result

        parameters["max_stopovers"] = 2
        return self._search(parameters, headers)

    def _search(self, parameters, headers):
        try:
            response = requests.get(
                url=f"{END_POINT}/v2/search",
                headers=headers,
                params=parameters,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            data = result.get("data", [])
            if not data:
                return None

            first_option = data[0]
            route = first_option.get("route", [])
            if len(route) < 2:
                return None

            outbound = route[0]
            inbound = route[-1]
            stopover_leg = route[1] if len(route) > 2 else None

            return FlightData(
                price=first_option["price"],
                fly_from_city=outbound["cityFrom"],
                fly_from_airport=outbound["flyFrom"],
                destination_city=inbound["cityFrom"],
                destination_airport=inbound["flyFrom"],
                out_date=outbound["local_departure"].split("T")[0],
                return_date=inbound["local_departure"].split("T")[0],
                via_city=stopover_leg["cityTo"] if stopover_leg else "",
                via_airport=stopover_leg["flyTo"] if stopover_leg else "",
            )
        except (requests.RequestException, KeyError, IndexError, ValueError):
            return None
