import pandas as pd
import numpy as np
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller
from typing import Optional, Tuple, Dict, Any, List
# Assuming Resampler is correctly imported from its relative path
from src.analytics.resampling import Resampler 

class PairsAnalyst:
    """
    Computes key pairs trading metrics for two time-aligned assets: 
    Hedge Ratio, Spread, Z-score, Rolling Correlation, and ADF Test.
    """
    def __init__(self, resampler: Resampler):
        self.resampler = resampler
        self.metadata: Dict[str, Any] = {} # To store non-time-series results like Hedge Ratio, ADF

    def _align_and_prepare_data(self, sym1: str, sym2: str, timeframe: str, lookback_minutes: int) -> Optional[pd.DataFrame]:
        """
        Retrieves resampled data for two symbols and aligns them by time index.
        Returns a DataFrame of aligned Close prices.
        """
        # Fetch resampled OHLCV data
        df1 = self.resampler.resample_to_ohlcv(sym1, timeframe, lookback_minutes)
        df2 = self.resampler.resample_to_ohlcv(sym2, timeframe, lookback_minutes)
        
        if df1 is None or df2 is None:
            return None

        # Align the two time series using a time index inner join
        # Inner join ensures we only analyze periods where both symbols have data
        combined_df = pd.merge(
            df1['Close'].rename(sym1),
            df2['Close'].rename(sym2),
            left_index=True,
            right_index=True,
            how='inner'
        )
        
        if combined_df.empty:
            print(f"[PairsAnalyst] Error: Merged data for {sym1} and {sym2} is empty after alignment.")
            return None
        
        return combined_df

    def calculate_hedge_ratio_and_spread(self, df_prices: pd.DataFrame, sym1: str, sym2: str) -> Tuple[float, pd.Series]:
        """
        Calculates the optimal hedge ratio (beta) using OLS regression 
        and computes the resulting spread (residuals).
        """
        # Y (Dependent variable) and X (Independent variable/Hedge asset)
        Y = np.log(df_prices[sym1])
        X = np.log(df_prices[sym2])

        # Add a constant (intercept) term to the independent variable for OLS
        X_with_const = sm.add_constant(X)
        
        # Fit the Ordinary Least Squares (OLS) model
        model = sm.OLS(Y, X_with_const, missing='drop') # missing='drop' handles NaNs
        results = model.fit()
        
        # The Hedge Ratio (beta) is the coefficient of X (sym2)
        hedge_ratio = results.params.get(sym2, np.nan)
        
        # Calculate the spread (residual): Spread = Y - (alpha + beta * X)
        spread = results.resid
        
        return hedge_ratio, spread

    def calculate_rolling_metrics(self, df_prices: pd.DataFrame, spread: pd.Series, window: int) -> Dict[str, pd.Series]:
        """
        Calculates rolling Z-score for the spread and rolling correlation between assets.
        """
        if window <= 0 or window > len(spread):
            # Use a sensible default or the length of the spread if window is invalid
            window = min(len(spread), 60) 
        
        # 1. Rolling Mean and Std Dev of the Spread
        rolling_mean = spread.rolling(window=window).mean()
        rolling_std = spread.rolling(window=window).std()
        
        # 2. Z-score calculation: Z = (Spread - Rolling Mean) / Rolling Std
        z_score = (spread - rolling_mean) / rolling_std
        
        # 3. Rolling Correlation between the two assets (Close prices)
        syms = list(df_prices.columns)
        rolling_corr = df_prices[syms[0]].rolling(window=window).corr(df_prices[syms[1]])
        
        return {
            'z_score': z_score.rename('Z_Score'),
            'rolling_correlation': rolling_corr.rename('Rolling_Correlation'),
            # Include rolling mean and std for spread visualization
            'rolling_spread_mean': rolling_mean.rename('Rolling_Mean'),
            'rolling_spread_std': rolling_std.rename('Rolling_Std')
        }

    def run_adf_test(self, spread: pd.Series) -> Dict[str, Any]:
        """
        Performs the Augmented Dickey-Fuller (ADF) test on the spread time series 
        to test for stationarity.
        Returns the test results.
        """
        # ADF requires non-NaN data. Drop NaNs introduced by OLS/rolling calculations.
        clean_spread = spread.dropna()
        
        if len(clean_spread) < 20: 
             return {"ADF_Test_Result": "Insufficient data points (min 20) for meaningful test."}
             
        try:
            # Perform the test. 'ct' (constant and trend) is a common choice
            result = adfuller(clean_spread, autolag='AIC')
            
            adf_output = {
                'ADF Statistic': round(result[0], 4),
                'p-value': round(result[1], 4),
                'Lags Used': result[2],
                'Number of Observations': result[3],
                'Critical Values': result[4],
                # Check for stationarity (p-value < 0.05 is the typical requirement)
                'Is_Stationary_95%': bool(result[1] < 0.05) 
            }
        except Exception as e:
            adf_output = {"ADF_Test_Result": f"ADF test failed: {e}"}
        
        return adf_output

    def run_full_analysis(self, sym1: str, sym2: str, timeframe: str, rolling_window: int, lookback_minutes: int = 720) -> Optional[pd.DataFrame]:
        """
        Orchestrates the entire pairs trading analysis pipeline, computes all metrics,
        and updates the metadata.
        """
        # 1. Prepare Data
        df_prices = self._align_and_prepare_data(sym1, sym2, timeframe, lookback_minutes)
        if df_prices is None:
            return None
            
        # 2. Calculate Hedge Ratio and Spread
        hedge_ratio, spread = self.calculate_hedge_ratio_and_spread(df_prices, sym1, sym2)
        
        # 3. Calculate Rolling Metrics (Z-score, Correlation, Mean, Std)
        rolling_metrics = self.calculate_rolling_metrics(df_prices, spread, rolling_window)
        
        # 4. Perform ADF Test
        adf_results = self.run_adf_test(spread)
        
        # 5. Compile Results into a single DataFrame
        final_df = pd.DataFrame({
            'Price_Y': df_prices[sym1],
            'Price_X': df_prices[sym2],
            'Spread': spread,
            'Z_Score': rolling_metrics['z_score'],
            'Rolling_Mean': rolling_metrics['rolling_spread_mean'],
            'Rolling_Std': rolling_metrics['rolling_spread_std'],
            'Rolling_Correlation': rolling_metrics['rolling_correlation']
        })
        
        # 6. Store Metadata
        self.metadata = {
            'Symbol_Y': sym1,
            'Symbol_X': sym2,
            'Timeframe': timeframe,
            'Rolling_Window': rolling_window,
            'Hedge_Ratio': round(hedge_ratio, 4) if not np.isnan(hedge_ratio) else np.nan,
            'ADF_Test_Results': adf_results
        }
        
        # Remove initial rows that contain NaNs due to the rolling window calculation
        # ADF and Hedge Ratio metadata will remain available via self.metadata
        return final_df.dropna()