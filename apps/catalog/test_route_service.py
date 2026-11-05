import json
import unittest
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from .services.routing import RoutingUnavailable, geocode, route_legs


class RouteServiceTests(unittest.TestCase):
    points = [{"lat": 55.70, "lng": 37.60}, {"lat": 55.75, "lng": 37.65}, {"lat": 55.76, "lng": 37.66}]

    def response(self, mocked, payload):
        mocked.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()

    @patch("apps.catalog.services.routing.urlopen")
    def test_provider_durations_are_summed_per_leg_without_reordering(self, mocked):
        self.response(mocked, {"route": {"legs": [
            {"status": "OK", "steps": [{"duration": 89, "length": 124}, {"duration": 61, "length": 80}]},
            {"status": "OK", "steps": [{"duration": 600, "length": 700}]},
        ]}})
        legs = route_legs(self.points, "walking", "private-test-key")
        self.assertEqual(legs, [{"seconds": 150, "meters": 204}, {"seconds": 600, "meters": 700}])
        request = mocked.call_args.args[0]
        query = parse_qs(urlparse(request.full_url).query)
        self.assertEqual(query["waypoints"], ["55.700000,37.600000|55.750000,37.650000|55.760000,37.660000"])
        self.assertEqual(query["mode"], ["walking"])
        self.assertEqual(query["optimize"], ["false"])
        self.assertEqual(mocked.call_args.kwargs["timeout"], 8)

    @patch("apps.catalog.services.routing.urlopen")
    def test_missing_and_invalid_legs_never_receive_guessed_times(self, mocked):
        for invalid in (None, -1, float("nan"), float("inf"), True, "600"):
            with self.subTest(invalid=invalid):
                self.response(mocked, {"route": {"legs": [
                    {"status": "OK", "steps": [{"duration": invalid, "length": 100}]},
                    {"status": "FAIL", "steps": []},
                ]}})
                self.assertEqual(route_legs(self.points, "walking", "key"), [
                    {"seconds": None, "meters": None}, {"seconds": None, "meters": None},
                ])

    @patch("apps.catalog.services.routing.urlopen")
    def test_incomplete_provider_response_cannot_shift_times_between_points(self, mocked):
        self.response(mocked, {"route": {"legs": [{"status": "OK", "steps": [{"duration": 60, "length": 100}]}]}})
        with self.assertRaises(RoutingUnavailable):
            route_legs(self.points, "walking", "key")

    @patch("apps.catalog.services.routing.urlopen")
    def test_network_and_http_errors_do_not_expose_the_key(self, mocked):
        for error in (TimeoutError("timeout"), URLError("offline"), HTTPError("https://api.routing.yandex.net/?apikey=private-test-key", 401, "private-test-key", {}, None)):
            mocked.side_effect = error
            with self.assertRaises(RoutingUnavailable) as caught:
                route_legs(self.points, "walking", "private-test-key")
            self.assertNotIn("private-test-key", str(caught.exception))

    @patch("apps.catalog.services.routing.urlopen")
    def test_malformed_and_oversized_json_are_rejected(self, mocked):
        for raw in (b"not json", b"[]", b"x" * 2_000_001):
            mocked.return_value.__enter__.return_value.read.return_value = raw
            with self.assertRaises(RoutingUnavailable):
                route_legs(self.points, "walking", "key")

    @patch("apps.catalog.services.routing.urlopen")
    def test_geocoder_preserves_longitude_latitude_order_and_readable_address(self, mocked):
        self.response(mocked, {"response": {"GeoObjectCollection": {"featureMember": [{"GeoObject": {
            "Point": {"pos": "37.6 55.7"},
            "metaDataProperty": {"GeocoderMetaData": {"Address": {"formatted": "Москва, адрес 1"}}},
        }}]}}})
        self.assertEqual(geocode("37.6,55.7", "geocoder-key", reverse=True), [{"lat": 55.7, "lng": 37.6, "label": "Москва, адрес 1"}])
        query = parse_qs(urlparse(mocked.call_args.args[0].full_url).query)
        self.assertEqual(query["results"], ["1"])

    @patch("apps.catalog.services.routing.urlopen")
    def test_empty_address_search_is_not_an_invented_origin(self, mocked):
        self.response(mocked, {"response": {"GeoObjectCollection": {"featureMember": []}}})
        self.assertEqual(geocode("несуществующий адрес", "key"), [])
