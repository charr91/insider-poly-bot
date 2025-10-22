"""
Backtesting Framework

Provides tools for historical data analysis and algorithm validation.
"""

from .graph_client import PolymarketGraphClient
from .historical_storage import HistoricalTradeStorage
from .data_loader import HistoricalDataLoader
from .simulation_engine import SimulationEngine, MarketState, VirtualAlert
from .outcome_tracker import (
    OutcomeTracker,
    AlertOutcome,
    OutcomeDirection,
    OutcomeResult
)
from .metrics_calculator import MetricsCalculator, PerformanceMetrics

__all__ = [
    'PolymarketGraphClient',
    'HistoricalTradeStorage',
    'HistoricalDataLoader',
    'SimulationEngine',
    'MarketState',
    'VirtualAlert',
    'OutcomeTracker',
    'AlertOutcome',
    'OutcomeDirection',
    'OutcomeResult',
    'MetricsCalculator',
    'PerformanceMetrics'
]
