from fastapi import APIRouter, HTTPException

from app.schemas.tracking import PredictionRequest, PredictionResponse
from app.services.prediction_service import prediction_service

router = APIRouter(prefix="/prediction", tags=["Prediction"])

@router.post("/compare", response_model=PredictionResponse)
def compare_prediction(req: PredictionRequest):
    """
    Computes an illustrative linear angular extrapolation trajectory
    and verifies against a comparison observation if provided.
    """
    try:
        return prediction_service.compute_prediction_and_verify(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction calculation error: {str(e)}")
