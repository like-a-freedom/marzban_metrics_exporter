import api
from fastapi import FastAPI
import prometheus_client as prom


api_client = api.PrometheusCollector()
app = FastAPI()

registry = prom.CollectorRegistry()
registry.register(api_client)

prom.REGISTRY.register(api_client)


@app.get("/metrics")
async def metrics():
    return prom.generate_latest(registry)
