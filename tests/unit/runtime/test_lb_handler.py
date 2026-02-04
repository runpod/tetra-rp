"""Unit tests for LoadBalancer handler factory."""

from runpod_flash.runtime.lb_handler import create_lb_handler


class TestExecuteEndpointStillWorks:
    """Tests to ensure /execute endpoint still works after manifest changes."""

    def test_execute_endpoint_still_available_with_live_load_balancer(self):
        """Verify /execute endpoint is still registered for LiveLoadBalancer."""
        app = create_lb_handler({}, include_execute=True)
        routes = [route.path for route in app.routes]

        assert "/execute" in routes

    def test_execute_endpoint_not_included_for_deployed(self):
        """Verify /execute endpoint is not registered for deployed LoadBalancer."""
        app = create_lb_handler({}, include_execute=False)
        routes = [route.path for route in app.routes]

        assert "/execute" not in routes
