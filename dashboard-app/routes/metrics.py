"""Metrics tab APIs: tailnet telemetry, bounded history and chart rates."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/api/metrics")
def api_metrics():
    """Collect observed tailnet telemetry and local project health."""
    try:
        from collectors.metrics import collect_all_metrics

        return JSONResponse(collect_all_metrics())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/metrics/history")
def api_metrics_history(window: str = "1h"):
    """Read bounded, allowlisted performance history from Prometheus."""
    if window not in ("1h", "6h", "24h"):
        return JSONResponse({"error": "Choose 1h, 6h, or 24h."}, status_code=422)
    try:
        from collectors.metrics import collect_metric_history

        return JSONResponse(collect_metric_history(window))
    except Exception:
        return JSONResponse(
            {"error": "Performance history is unavailable."}, status_code=503
        )


@router.get("/api/metrics/rates")
def api_metrics_rates(window: str = "1h"):
    """Network/disk rates, probe timeline and log volume for the Metrics charts."""
    if window not in ("1h", "6h", "24h"):
        return JSONResponse({"error": "Choose 1h, 6h, or 24h."}, status_code=400)
    try:
        from collectors.metric_charts import collect_chart_history

        return JSONResponse(collect_chart_history(window))
    except Exception:
        return JSONResponse({"error": "Chart history is unavailable."}, status_code=503)
