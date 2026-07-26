"""ExperimentGuard: reproducible game A/B-test evaluation without dependencies."""

from .analysis import ExperimentAnalyzer
from .models import ExperimentResult

__all__ = ["ExperimentAnalyzer", "ExperimentResult"]
__version__ = "1.0.0"

