from sqlalchemy import create_engine, Column, Float, String, Integer
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any, List

# --- Configuration ---
# Define the database file path
DATABASE_FILE = "data/analytics.db"

# 🛑 CORRECTED LINE: Removed "yes". The correct dialect prefix is 'sqlite:///'
DATABASE_URL = f"sqlite:///{DATABASE_FILE}" 

# Base class for declarative class definitions
Base = declarative_base()

# --- Database Models ---
class TickData(Base):
    """SQLAlchemy model for storing raw tick data from Binance."""
    __tablename__ = 'raw_ticks'

    # We use symbol + raw_ts_ms for a unique primary key to prevent duplication
    id = Column(String, primary_key=True)  
    symbol = Column(String, index=True, nullable=False)
    ts = Column(String, index=True, nullable=False)      # ISO formatted timestamp
    price = Column(Float, nullable=False)
    size = Column(Float, nullable=False)
    raw_ts_ms = Column(Float, index=True, nullable=False)  # Original timestamp in milliseconds

    def __repr__(self):
        return f"<Tick(symbol='{self.symbol}', price={self.price}, ts={self.ts})>"

class BarData(Base):
    """SQLAlchemy model for storing resampled OHLCV data."""
    __tablename__ = 'ohlcv_bars'
    
    # Combined primary key: Symbol + Timeframe + OpenTime
    id = Column(String, primary_key=True) 
    symbol = Column(String, index=True, nullable=False)
    timeframe = Column(String, index=True, nullable=False) # e.g., '1s', '1m', '5m'
    open_time = Column(String, index=True, nullable=False)
    
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    def __repr__(self):
        return f"<Bar(symbol='{self.symbol}', tf='{self.timeframe}', close={self.close})>"

# --- Database Manager Class ---
class DBManager:
    """Manages database connection and CRUD operations for the application."""
    def __init__(self):
        # Create a database engine (connect to the file)
        self.engine = create_engine(DATABASE_URL)
        # Create all defined tables (raw_ticks, ohlcv_bars) if they don't exist
        Base.metadata.create_all(self.engine)
        print(f"[{self.__class__.__name__}] Database initialized at: {DATABASE_FILE}")

    def save_tick(self, tick_data: Dict[str, Any]):
        """
        Saves a single normalized tick dictionary to the raw_ticks table.
        This function will be used as the callback from the WebSocket client.
        """
        # Create a unique ID to ensure primary key constraint
        unique_id = f"{tick_data['symbol']}_{tick_data['raw_ts_ms']}"
        
        new_tick = TickData(
            id=unique_id,
            symbol=tick_data['symbol'],
            ts=tick_data['ts'],
            price=tick_data['price'],
            size=tick_data['size'],
            raw_ts_ms=tick_data['raw_ts_ms']
        )
        
        # Use a session for transaction management
        try:
            with Session(self.engine) as session:
                session.add(new_tick)
                session.commit()
        except SQLAlchemyError as e:
            # Catch primary key constraint violations and other common DB errors
            if 'UNIQUE constraint failed' in str(e):
                pass 
            else:
                print(f"[{self.__class__.__name__}] Database error saving tick: {e}")
                session.rollback()

    def get_raw_ticks(self, symbol: str, start_time_ms: float) -> List[Dict[str, Any]]:
        """
        Retrieves raw ticks for a given symbol starting from a specified time.
        """
        with Session(self.engine) as session:
            ticks = session.query(TickData).filter(
                TickData.symbol == symbol,
                TickData.raw_ts_ms >= start_time_ms
            ).order_by(TickData.raw_ts_ms).all()
            
            # Convert SQLAlchemy objects back to a list of dictionaries for easier use with Pandas
            return [
                {
                    'ts': tick.ts,
                    'price': tick.price,
                    'size': tick.size,
                    'raw_ts_ms': tick.raw_ts_ms
                } 
                for tick in ticks
            ]