"""Lightweight graph package exports.

Keep package import cheap so tests can import submodules like
``tradingagents.graph.propagation`` without pulling the full trading graph
and every data dependency into collection time.
"""

from .conditional_logic import ConditionalLogic
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor

__all__ = [
    "ConditionalLogic",
    "Propagator",
    "Reflector",
    "SignalProcessor",
]
