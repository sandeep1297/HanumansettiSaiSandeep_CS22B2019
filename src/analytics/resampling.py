import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from src.storage.db_manager import DBManager 

class Resampler:
    """
    Handles retrieval of raw ticks and resampling into OHLCV bars.
    """
    def __init__(self, db_manager: DBManager):
        self.db = db_manager

    def _get_ticks_for_resampling(self, symbol: str, lookback_minutes: int) -> Optional[pd.DataFrame]:
        """
        Retrieves raw tick data from the database for a given lookback period
        and converts it into a time-indexed Pandas DataFrame.
        """
        # Calculate the starting time in milliseconds (the unit used in raw_ts_ms)
        start_time = datetime.now() - timedelta(minutes=lookback_minutes)
        start_time_ms = start_time.timestamp() * 1000

        # Fetch the raw data using the DBManager interface
        raw_data_list = self.db.get_raw_ticks(symbol, start_time_ms)
        
        if not raw_data_list:
            return None

        # Convert list of dicts to DataFrame
        df = pd.DataFrame(raw_data_list)
        
        # Use format='ISO8601' for robust datetime parsing (Fixes previous ValueError)
        df['ts'] = pd.to_datetime(df['ts'], format='ISO8601') 
        
        df.set_index('ts', inplace=True)
        
        # Ensure price and size are numerical
        df['price'] = pd.to_numeric(df['price'])
        df['size'] = pd.to_numeric(df['size'])
        
        return df

    def resample_to_ohlcv(self, symbol: str, timeframe: str, lookback_minutes: int = 60) -> Optional[pd.DataFrame]:
        """
        Retrieves raw ticks and resamples them into OHLCV bars for the given timeframe.
        
        Args:
            symbol: The trading symbol (e.g., 'BTCUSDT').
            timeframe: The resampling frequency ('1S', '1T', '5T').
            lookback_minutes: How far back to query data from the database.
            
        Returns:
            A DataFrame of OHLCV bars, or None if no data is found.
        """
        df_ticks = self._get_ticks_for_resampling(symbol, lookback_minutes)
        
        if df_ticks is None:
            return None

        # 🛑 FIX APPLIED HERE: Replace the deprecated 'T' (Time) alias with 'min' (Minute)
        # This addresses the FutureWarning you were seeing (e.g., '1T' -> '1min')
        safe_timeframe = timeframe.replace('T', 'min')

        # Apply the pandas resampling function using the specified timeframe
        ohlcv_data = df_ticks['price'].resample(safe_timeframe, label='right', closed='right').ohlc()
        ohlcv_volume = df_ticks['size'].resample(safe_timeframe, label='right', closed='right').sum()

        # Combine OHLC and Volume
        ohlcv_df = pd.DataFrame({
            'Open': ohlcv_data['open'],
            'High': ohlcv_data['high'],
            'Low': ohlcv_data['low'],
            'Close': ohlcv_data['close'],
            'Volume': ohlcv_volume
        })
        
        # Remove any bars where the Open price is missing (no trades occurred in that interval)
        ohlcv_df.dropna(subset=['Open'], inplace=True)
        
        if ohlcv_df.empty:
            return None
            
        return ohlcv_df.rename_axis('Open_Time')