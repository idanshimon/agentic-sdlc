"""OpenTelemetry → App Insights. Captures the two cost dimensions the orchestrator
actually owns: re-run cost (tokens) and human-attention cost (gate wall-clock).
See design.md §7 (four-dimensional cost-per-decision)."""
from __future__ import annotations
import logging
from typing import Optional

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .config import settings

_logger = logging.getLogger("orchestrator.telemetry")
_initialised = False
_tracer: Optional[trace.Tracer] = None
_tokens_counter = None
_cost_counter = None
_gate_seconds_hist = None


def init_telemetry() -> None:
    """Wire OTel → App Insights once at app startup (design.md §7 hot-tier)."""
    global _initialised, _tracer, _tokens_counter, _cost_counter, _gate_seconds_hist
    if _initialised:
        return
    resource = Resource.create({"service.name": "agentic-sdlc-orchestrator"})
    # azure-monitor-opentelemetry exporters are optional; fall back to console-quiet noop
    # so the demo still works without the exporter package installed.
    try:
        from azure.monitor.opentelemetry.exporter import (
            AzureMonitorMetricExporter, AzureMonitorTraceExporter,
        )
        conn = settings.appi_conn
        if conn:
            trace_provider = TracerProvider(resource=resource)
            trace_provider.add_span_processor(
                BatchSpanProcessor(AzureMonitorTraceExporter(connection_string=conn))
            )
            trace.set_tracer_provider(trace_provider)
            meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[PeriodicExportingMetricReader(
                    AzureMonitorMetricExporter(connection_string=conn),
                    export_interval_millis=30_000,
                )],
            )
            metrics.set_meter_provider(meter_provider)
    except Exception as exc:  # pragma: no cover — demo resilience
        _logger.warning("App Insights exporter unavailable: %s", exc)
    _tracer = trace.get_tracer("orchestrator")
    meter = metrics.get_meter("orchestrator")
    _tokens_counter = meter.create_counter(
        "agentic.tokens.total", unit="tokens", description="Re-run cost (token usage).",
    )
    _cost_counter = meter.create_counter(
        "agentic.cost.usd", unit="USD", description="Estimated re-run USD cost.",
    )
    _gate_seconds_hist = meter.create_histogram(
        "agentic.gate.wall_clock_seconds", unit="s",
        description="Human-attention cost (gate wall-clock, design.md §7).",
    )
    _initialised = True


def record_tokens(stage: str, agent: str, tokens: int, usd: float) -> None:
    """Re-run cost dim — one record per APIM model call."""
    if _tokens_counter is None:
        return
    attrs = {"stage": stage, "agent": agent}
    _tokens_counter.add(tokens, attrs)
    _cost_counter.add(usd, attrs)


def record_gate_wall_clock(stage: str, seconds: float) -> None:
    """Human-attention cost dim — wall-clock a gate stayed open."""
    if _gate_seconds_hist is None:
        return
    _gate_seconds_hist.record(seconds, {"stage": stage})


def span(name: str):
    """Context-manager span helper (no-op when telemetry not initialised)."""
    if _tracer is None:
        from contextlib import nullcontext
        return nullcontext()
    return _tracer.start_as_current_span(name)
