import os
import httpx
import prometheus_client as prom
from dotenv import load_dotenv

load_dotenv()

MARZBAN_URL = os.getenv("MARZBAN_URL")
MARZBAN_USERNAME = os.getenv("MARZBAN_USERNAME")
MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD")


class MarzbanAPI:
    def __init__(self):
        self.client = httpx.Client(
            base_url=f"{MARZBAN_URL}/api", follow_redirects=True, timeout=30
        )
        self.token = self._get_token()

    def _get_token(self) -> dict | None:
        try:
            request = self.client.post(
                "/admin/token",
                data={"username": MARZBAN_USERNAME, "password": MARZBAN_PASSWORD},
            ).json()["access_token"]
            print("Token successfully acquired!")
            return request
        except httpx.HTTPStatusError as e:
            raise Exception(e)

    def _fetch(self, endpoint: str) -> dict:
        try:
            response = self.client.get(
                endpoint, headers={"Authorization": f"Bearer {self.token}"}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"Error fetching data from {endpoint}: {e}")

    def fetch_nodes_data(self) -> dict:
        return self._fetch("/nodes")

    def fetch_nodes_usage_data(self) -> dict:
        return self._fetch("/nodes/usage")

    def fetch_system_data(self) -> dict:
        return self._fetch("/system")

    def fetch_core_data(self) -> dict:
        return self._fetch("/core")

    def fetch_users_data(self) -> dict:
        return self._fetch("/users")


class PrometheusCollector(prom.CollectorRegistry):
    def __init__(self, api_client: MarzbanAPI = MarzbanAPI()):
        self.registry = prom.CollectorRegistry()
        self.api_client = api_client

        self.metrics = {
            "node_usage_coefficient": prom.metrics_core.GaugeMetricFamily(
                "node_usage_coefficient", "Node usage coefficient", labels=["node_name"]
            ),
            "node_address": prom.metrics_core.GaugeMetricFamily(
                "node_info",
                "Node address, port, API port, xray version, and status",
                labels=[
                    "node_name",
                    "address",
                    "port",
                    "api_port",
                    "xray_version",
                    "status",
                ],
            ),
            "node_uplink": prom.metrics_core.GaugeMetricFamily(
                "node_uplink_bytes",
                "Node uplink traffic in bytes",
                labels=["node_name"],
            ),
            "node_downlink": prom.metrics_core.GaugeMetricFamily(
                "node_downlink_bytes",
                "Node downlink traffic in bytes",
                labels=["node_name"],
            ),
            "system_version": prom.metrics_core.GaugeMetricFamily(
                "system_version", "System version"
            ),
            "system_mem_total": prom.metrics_core.GaugeMetricFamily(
                "system_memory_total_bytes", "Total system memory in bytes"
            ),
            "system_mem_used": prom.metrics_core.GaugeMetricFamily(
                "system_memory_used_bytes", "Used system memory in bytes"
            ),
            "system_cpu_usage": prom.metrics_core.GaugeMetricFamily(
                "system_cpu_usage_percent", "System CPU usage percentage"
            ),
            "system_total_users": prom.metrics_core.GaugeMetricFamily(
                "system_total_users", "Total number of users in the system"
            ),
            "system_active_users": prom.metrics_core.GaugeMetricFamily(
                "system_active_users", "Number of active users in the system"
            ),
            "system_incoming_bandwidth": prom.metrics_core.GaugeMetricFamily(
                "system_incoming_bandwidth_bytes", "Total incoming bandwidth in bytes"
            ),
            "system_outgoing_bandwidth": prom.metrics_core.GaugeMetricFamily(
                "system_outgoing_bandwidth_bytes", "Total outgoing bandwidth in bytes"
            ),
            "core_started": prom.metrics_core.GaugeMetricFamily(
                "core_started", "Core started status"
            ),
            "total_users": prom.metrics_core.GaugeMetricFamily(
                "total_users", "Total number of users"
            ),
            "user_traffic": prom.metrics_core.GaugeMetricFamily(
                "user_lifetime_used_traffic_bytes",
                "Lifetime used traffic per user in bytes",
                labels=["username"],
            ),
        }

    def collect(self):
        self._collect_nodes_metrics()
        self._collect_nodes_usage_metrics()
        self._collect_system_metrics()
        self._collect_core_metrics()
        self._collect_users_metrics()

        yield from self.metrics.values()

    def _collect_nodes_metrics(self):
        nodes = self.api_client.fetch_nodes_data()
        for node in nodes:
            node_name = node.get("name", "unknown")
            self.metrics["node_usage_coefficient"].add_metric(
                [node_name], node.get("usage_coefficient", 0)
            )
            self.metrics["node_address"].add_metric(
                [
                    str(node_name),
                    str(node.get("address", "unknown")),
                    str(node.get("port", "unknown")),
                    str(node.get("api_port", "unknown")),
                    str(node.get("xray_version", "unknown")),
                    str(node.get("status", "unknown")),
                ],
                1,  # Static value since this metric reflects node info
            )

    def _collect_nodes_usage_metrics(self):
        usage_data = self.api_client.fetch_nodes_usage_data()
        for usage in usage_data.get("usages", []):
            node_name = usage.get("node_name", "unknown")
            self.metrics["node_uplink"].add_metric([node_name], usage.get("uplink", 0))
            self.metrics["node_downlink"].add_metric(
                [node_name], usage.get("downlink", 0)
            )

    def _collect_system_metrics(self):
        system_data = self.api_client.fetch_system_data()
        self.metrics["system_version"].add_metric(
            [], 1
        )  # Static value just to represent the version presence
        self.metrics["system_mem_total"].add_metric([], system_data.get("mem_total", 0))
        self.metrics["system_mem_used"].add_metric([], system_data.get("mem_used", 0))
        self.metrics["system_cpu_usage"].add_metric([], system_data.get("cpu_usage", 0))
        self.metrics["system_total_users"].add_metric(
            [], system_data.get("total_user", 0)
        )
        self.metrics["system_active_users"].add_metric(
            [], system_data.get("users_active", 0)
        )
        self.metrics["system_incoming_bandwidth"].add_metric(
            [], system_data.get("incoming_bandwidth", 0)
        )
        self.metrics["system_outgoing_bandwidth"].add_metric(
            [], system_data.get("outgoing_bandwidth", 0)
        )

    def _collect_core_metrics(self):
        core_data = self.api_client.fetch_core_data()
        self.metrics["core_started"].add_metric(
            [], int(core_data.get("started", False))
        )

    def _collect_users_metrics(self):
        users_data = self.api_client.fetch_users_data()
        users = users_data.get("users", [])
        self.metrics["total_users"].add_metric([], len(users))
        for user in users:
            username = user.get("username", "unknown")
            traffic = user.get("lifetime_used_traffic", 0)
            self.metrics["user_traffic"].add_metric([username], traffic)
