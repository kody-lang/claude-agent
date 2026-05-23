from unittest.mock import patch, MagicMock
import pytest
import server


def _mock_resp(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


class TestSearchDeliveries:
    @patch("server.requests.request")
    def test_returns_formatted_deliveries(self, mock_req):
        mock_req.return_value = _mock_resp([
            {"id": "123", "customer_name": "John Doe", "address": "123 Main St", "status": "pending"}
        ])
        result = server.search_deliveries("jj")
        assert "123" in result
        assert "John Doe" in result
        assert "pending" in result

    @patch("server.requests.request")
    def test_uses_jj_api_key(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.search_deliveries("jj")
        headers = mock_req.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-jj-key"

    @patch("server.requests.request")
    def test_uses_townsend_api_key(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.search_deliveries("townsend")
        headers = mock_req.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-townsend-key"

    @patch("server.requests.request")
    def test_empty_returns_no_deliveries_message(self, mock_req):
        mock_req.return_value = _mock_resp([])
        assert server.search_deliveries("jj") == "No deliveries found."

    @patch("server.requests.request")
    def test_passes_date_param(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.search_deliveries("jj", date="2026-05-23")
        assert mock_req.call_args[1]["params"]["date"] == "2026-05-23"

    @patch("server.requests.request")
    def test_passes_status_param(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.search_deliveries("jj", status="delivered")
        assert mock_req.call_args[1]["params"]["status"] == "delivered"


class TestGetDelivery:
    @patch("server.requests.request")
    def test_returns_json_string(self, mock_req):
        mock_req.return_value = _mock_resp({"id": "456", "status": "delivered"})
        result = server.get_delivery("jj", "456")
        assert "456" in result
        assert "delivered" in result

    @patch("server.requests.request")
    def test_url_contains_order_id(self, mock_req):
        mock_req.return_value = _mock_resp({})
        server.get_delivery("townsend", "999")
        url = mock_req.call_args[0][1]
        assert "999" in url


class TestGetRoutes:
    @patch("server.requests.request")
    def test_returns_formatted_routes(self, mock_req):
        mock_req.return_value = _mock_resp([
            {"id": "R1", "name": "Route A", "driver_name": "Bob", "stop_count": 5}
        ])
        result = server.get_routes("jj")
        assert "R1" in result
        assert "Bob" in result
        assert "5" in result

    @patch("server.requests.request")
    def test_empty_returns_no_routes_message(self, mock_req):
        mock_req.return_value = _mock_resp([])
        assert server.get_routes("jj") == "No routes found."

    @patch("server.requests.request")
    def test_passes_date_param(self, mock_req):
        mock_req.return_value = _mock_resp([])
        server.get_routes("jj", date="2026-05-24")
        assert mock_req.call_args[1]["params"]["date"] == "2026-05-24"
