"""Hospital comparison statistical analysis module."""

from .hospital_statistics import (
    HospitalStatistics,
    AnalysisResult,
    ShapiroResult,
    TTestResult,
    WilcoxonResult,
)

__all__ = [
    "HospitalStatistics",
    "AnalysisResult",
    "ShapiroResult",
    "TTestResult",
    "WilcoxonResult",
]
