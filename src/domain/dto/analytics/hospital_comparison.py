"""DTOs for hospital comparison analysis results."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ShapiroTestDTO(BaseModel):
    """Shapiro-Wilk normality test result."""

    statistic: float = Field(description="W statistic from Shapiro-Wilk test")
    p_value: float = Field(description="P-value of the test")
    is_normal: bool = Field(description="Whether data follows normal distribution (p > 0.05)")


class ComparisonTestDTO(BaseModel):
    """Statistical comparison test result (t-test or Wilcoxon)."""

    test_type: Literal["t-test", "wilcoxon"] = Field(description="Type of test performed")
    statistic: float = Field(description="Test statistic (t-statistic or U-statistic)")
    p_value: float = Field(description="P-value of the test")
    is_significant: bool = Field(description="Whether difference is significant (p < 0.05)")


class HospitalDatasetInfo(BaseModel):
    """Information about a hospital dataset."""

    hospital_id: Optional[str] = Field(None, description="Hospital identifier")
    hospital_name: Optional[str] = Field(None, description="Hospital name")
    sample_size: int = Field(description="Number of observations")
    shapiro_test: ShapiroTestDTO = Field(description="Normality test result")


class HospitalComparisonResult(BaseModel):
    """Complete hospital comparison analysis result."""

    schema_version: int = Field(default=1, description="Schema version")
    timestamp: datetime = Field(description="When the analysis was performed")
    
    hospital_1: HospitalDatasetInfo = Field(description="First hospital data and tests")
    hospital_2: HospitalDatasetInfo = Field(description="Second hospital data and tests")
    
    comparison_test: ComparisonTestDTO = Field(description="Statistical comparison test result")
    
    summary: str = Field(description="Human-readable summary of results")
    interpretation: str = Field(description="Interpretation of the statistical test")

    class Config:
        json_schema_extra = {
            "example": {
                "schema_version": 1,
                "timestamp": "2026-01-23T10:30:00",
                "hospital_1": {
                    "hospital_id": "H001",
                    "hospital_name": "Hospital A",
                    "sample_size": 150,
                    "shapiro_test": {
                        "statistic": 0.985,
                        "p_value": 0.082,
                        "is_normal": True
                    }
                },
                "hospital_2": {
                    "hospital_id": "H002",
                    "hospital_name": "Hospital B",
                    "sample_size": 145,
                    "shapiro_test": {
                        "statistic": 0.982,
                        "p_value": 0.065,
                        "is_normal": True
                    }
                },
                "comparison_test": {
                    "test_type": "t-test",
                    "statistic": -2.45,
                    "p_value": 0.015,
                    "is_significant": True
                },
                "summary": "Statistical comparison between Hospital A and Hospital B",
                "interpretation": "The two hospitals show statistically different door-to-needle times."
            }
        }
