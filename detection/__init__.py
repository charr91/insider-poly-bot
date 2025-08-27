"""
Detection Module
Contains all detection algorithms for unusual trading patterns
"""

from .volume_detector import VolumeDetector
from .whale_detector import WhaleDetector
from .price_detector import PriceDetector
from .coordination_detector import CoordinationDetector

__all__ = [
    'VolumeDetector',
    'WhaleDetector', 
    'PriceDetector',
    'CoordinationDetector'
]