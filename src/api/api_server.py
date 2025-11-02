from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import uvicorn # Required to run the application

# Import core modules
# NOTE: These paths assume you are running the API from the project root directory
from src.storage.db_manager import DBManager
from src.analytics.resampling import Resampler
from src.analytics.pairs_trading import PairsAnalyst

# --- Global Initialization ---

# Initialize the core components. These objects are heavy, so they should be singleton instances.
# In a robust system, this initialization would occur only after the DB connection is confirmed.
try:
    DB_MANAGER = DBManager()
    RESAMPLER = Resampler(DB_MANAGER)
    PAIRS_ANALYST = PairsAnalyst(RESAMPLER)
    print("[API] Core analytics components initialized successfully.")
except Exception as e:
    # Critical failure if DB or dependencies fail to load
    print(f"[API] CRITICAL ERROR during core component initialization: {e}")
    # You might want to halt the process here, but we proceed for demonstration

app = FastAPI(
    title="Quant Analytics API",
    description="Backend API for real-time crypto pairs trading analysis.",
    version="1.0.0"
)

# --- Pydantic Models for API Contract ---

# Request body model for the analysis endpoint
class AnalysisRequest(BaseModel):
    symbol1: str = Field(..., example="BTCUSDT", description="Dependent symbol (Y) for regression.")
    symbol2: str = Field(..., example="ETHUSDT", description="Independent symbol (X) for regression/hedge.")
    timeframe: str = Field("1T", example="5T", description="Resampling frequency (e.g., '1T' for 1 min, '5T' for 5 min).")
    rolling_window: int = Field(60, description="Window size for rolling Z-score and Correlation.")
    lookback_minutes: int = Field(720, description="How many minutes of historical data to analyze.")

# --- API Endpoints ---

@app.post("/api/v1/analysis")
async def get_pairs_analysis(request: AnalysisRequest):
    """
    Runs the full pairs trading analysis pipeline based on user parameters 
    and returns time-series data (for charts) and static metadata.
    """
    try:
        # Run the full analysis pipeline
        df_results = PAIRS_ANALYST.run_full_analysis(
            sym1=request.symbol1,
            sym2=request.symbol2,
            timeframe=request.timeframe,
            rolling_window=request.rolling_window,
            lookback_minutes=request.lookback_minutes
        )
        
        if df_results is None or df_results.empty:
            raise HTTPException(status_code=404, detail="Insufficient data to perform analysis or data frame is empty.")

        # Convert the time-series DataFrame to a structured list of dictionaries
        # Timestamp index is converted to a string field 'Open_Time'
        timeseries_data = df_results.reset_index().rename(columns={'Open_Time': 'ts'}).to_dict(orient="records")

        # Retrieve the metadata (Hedge Ratio, ADF results)
        metadata = PAIRS_ANALYST.metadata

        return {
            "status": "success",
            "metadata": metadata,
            "timeseries_data": timeseries_data
        }

    except HTTPException:
        # Re-raise explicit HTTP exceptions
        raise
    except Exception as e:
        print(f"[API] Analysis failed: {e}")
        # Return a generic 500 error for unexpected backend issues
        raise HTTPException(status_code=500, detail=f"Internal Server Error during analysis.")


@app.get("/api/v1/live_stats")
async def get_live_stats():
    """
    Provides the latest (most recent) computed key metrics for near-real-time updates.
    This fetches the latest tick data and runs a micro-analysis.
    """
    
    # We use a very short lookback window to get near-real-time data with low latency
    # Defaulting to the pre-configured BTC/ETH pair
    LIVE_SYMS = ["BTCUSDT", "ETHUSDT"]
    
    # Run a small analysis on recent data (e.g., last 10 minutes)
    df_results = PAIRS_ANALYST.run_full_analysis(
        sym1=LIVE_SYMS[0], sym2=LIVE_SYMS[1], 
        timeframe="1T", rolling_window=20, # Use a small window for fast calc
        lookback_minutes=10 # Only query the last 10 minutes
    )
    
    if df_results is None or df_results.empty:
         return {"latest_z_score": None, "latest_price_y": None, "latest_price_x": None}

    latest_row = df_results.iloc[-1]
    
    return {
        "status": "live",
        "latest_z_score": round(latest_row['Z_Score'], 4),
        "latest_spread": round(latest_row['Spread'], 4),
        "latest_price_y": round(latest_row['Price_Y'], 2),
        "latest_price_x": round(latest_row['Price_X'], 2),
        "current_time": latest_row.name.isoformat() 
    }

# --- Utility Endpoints ---

@app.get("/api/v1/symbols")
def get_supported_symbols():
    """Returns the list of symbols currently being ingested."""
    # This list should match the symbols defined in app.py
    return {"symbols": ["BTCUSDT", "ETHUSDT"]}