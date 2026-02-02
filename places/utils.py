"""Utility helpers for place-related services."""
import requests

def geocode_location(location_text):
    """Convert postcode or address into latitude and longitude using postcodes.io.

    :param location_text: Postcode or address string.
    :return: Tuple of (latitude, longitude) or (None, None) if lookup fails.
    :rtype: tuple[float | None, float | None]
    """

    url = f"https://api.postcodes.io/postcodes/{location_text}"
    response = requests.get(url, timeout=5)

    if response.status_code != 200:
        return None, None

    data = response.json()

    if data.get('status') != 200:
        return None, None

    result = data.get('result')
    if not result:
        return None, None

    return result['latitude'], result['longitude']
