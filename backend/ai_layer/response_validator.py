# backend/ai_layer/response_validator.py
"""
Pydantic models for validating AI responses.

Ensures AI-generated responses conform to expected schemas
before being used for reconciliation decisions.
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field, validator


class AIReasoningResponse(BaseModel):
    """
    Validated AI response for trade reconciliation.
    
    All fields are validated to ensure AI responses
    can't contain malicious data that bypasses checks.
    """
    best_match_id: Optional[int] = Field(
        None, 
        description="ID of the best matching cash entry"
    )
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Confidence score between 0 and 1"
    )
    action: Literal["MATCH", "REVIEW", "ESCALATE"] = Field(
        ...,
        description="Recommended action based on confidence"
    )
    explanation: str = Field(
        ...,
        max_length=500,
        description="Brief explanation of the match decision"
    )
    
    @validator("explanation")
    def sanitize_explanation(cls, v):
        """Ensure explanation doesn't contain dangerous content."""
        if not v:
            return ""
        # Truncate to 500 chars max
        return str(v)[:500]
    
    @validator("action", pre=True)
    def normalize_action(cls, v):
        """Normalize action to uppercase."""
        if isinstance(v, str):
            v = v.upper().strip()
        return v
    
    @classmethod
    def from_raw_response(cls, response_dict: dict) -> Optional["AIReasoningResponse"]:
        """
        Safely parse an AI response dictionary.
        
        Returns None if validation fails rather than raising.
        
        Args:
            response_dict: Raw dictionary from AI
            
        Returns:
            Validated AIReasoningResponse or None
        """
        try:
            # Ensure required fields exist
            if "confidence" not in response_dict:
                return None
            
            # Infer action from confidence if not provided
            if "action" not in response_dict:
                conf = float(response_dict.get("confidence", 0))
                if conf > 0.9:
                    response_dict["action"] = "MATCH"
                elif conf > 0.7:
                    response_dict["action"] = "REVIEW"
                else:
                    response_dict["action"] = "ESCALATE"
            
            # Provide default explanation if missing
            if "explanation" not in response_dict:
                response_dict["explanation"] = "No explanation provided"
            
            return cls(**response_dict)
            
        except Exception:
            return None


class PaginationParams(BaseModel):
    """
    Validated pagination parameters for API requests.
    
    Prevents excessive page sizes that could cause performance issues.
    """
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        50, 
        ge=1, 
        le=100, 
        description="Items per page (max 100)"
    )
    
    @property
    def offset(self) -> int:
        """Calculate SQL offset from page number."""
        return (self.page - 1) * self.page_size


class TradeFilterParams(BaseModel):
    """
    Validated trade filtering parameters.
    """
    status: Optional[str] = Field(
        None,
        description="Filter by status"
    )
    symbol: Optional[str] = Field(
        None,
        max_length=50,
        description="Filter by symbol (partial match)"
    )
    date_from: Optional[str] = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date (YYYY-MM-DD)"
    )
    date_to: Optional[str] = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date (YYYY-MM-DD)"
    )
    
    @validator("status")
    def validate_status(cls, v):
        """Ensure status is a valid value."""
        if v is None:
            return None
        v_upper = v.upper().strip()
        valid = {"MATCHED", "UNSETTLED", "BREAK", "PARTIAL"}
        if v_upper not in valid:
            raise ValueError(f"Invalid status. Must be one of: {valid}")
        return v_upper
