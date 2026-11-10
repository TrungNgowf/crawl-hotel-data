from .agoda import crawl_agoda
from .booking import crawl_booking
from .google import crawl_google
from .trip import crawl_trip

SITES = {
    "agoda": ("Agoda", "agoda_url", crawl_agoda),
    "booking": ("Booking.com", "booking_url", crawl_booking),
    "trip": ("Trip.com", "trip_url", crawl_trip),
    "google": ("Google Hotels", "google_url", crawl_google),
}
