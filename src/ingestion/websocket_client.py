import asyncio
import json
import websockets
from typing import List, Dict, Any, Callable
from datetime import datetime
import time

# --- Configuration ---
BINANCE_WSS_BASE = "wss://fstream.binance.com/ws/"

# --- Core Functions ---

def normalize_tick_data(raw_data: str) -> Dict[str, Any] | None:
    """
    Parses a raw Binance WebSocket message and normalizes the trade event.
    Returns a dictionary with 'symbol', 'ts', 'price', and 'size'.
    """
    try:
        j = json.loads(raw_data)
        # Check for a trade event ('e' stands for event type)
        if j.get('e') == 'trade':
            # Use 'T' (trade time) from the original message
            ts_ms = j.get('T')
            
            return {
                'symbol': j.get('s').upper(),
                'ts': datetime.fromtimestamp(ts_ms / 1000.0).isoformat(),
                'price': float(j.get('p')),
                'size': float(j.get('q')),
                'raw_ts_ms': ts_ms # Critical for accurate time-series alignment and primary key
            }
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # In a production setting, this would be routed to a logging system
        print(f"[ERROR] Failed to process message: {raw_data[:50]}... Error: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] Unexpected error in normalization: {e}")
        return None
    return None

async def connect_and_listen(symbol: str, data_callback: Callable):
    """
    Connects to a single Binance Futures trade stream and continuously processes messages.
    Includes built-in reconnect logic.
    """
    symbol_upper = symbol.upper()
    symbol_lower = symbol.lower()
    
    # WebSocket endpoint for a single trade stream
    uri = f"{BINANCE_WSS_BASE}{symbol_lower}@trade"
    
    print(f"[{symbol_upper}] Starting WebSocket connection...")

    # The 'async for' handles the main reconnect loop automatically
    while True:
        try:
            # Use websockets.connect as a context manager for reliable connection handling
            async with websockets.connect(uri) as websocket:
                print(f"[{symbol_upper}] Connection established successfully.")
                
                # Inner loop for message reception
                while True:
                    message = await websocket.recv()
                    tick = normalize_tick_data(message)
                    if tick:
                        # Call the provided handler (e.g., db_manager.save_tick)
                        data_callback(tick)
        
        except websockets.ConnectionClosedOK:
            # Clean closure
            print(f"[{symbol_upper}] Connection closed gracefully.")
            break
        except websockets.ConnectionClosed as e:
            # Connection closed due to an error, attempt reconnect
            print(f"[{symbol_upper}] Connection closed (Code: {e.code}). Reconnecting in 5s...")
            await asyncio.sleep(5)
        except ConnectionRefusedError:
            print(f"[{symbol_upper}] Connection refused. Retrying in 10s...")
            await asyncio.sleep(10)
        except Exception as e:
            # Catch all other exceptions (e.g., DNS error, network issue)
            print(f"[{symbol_upper}] General error: {e}. Retrying in 10s...")
            await asyncio.sleep(10)


def start_ingestion(symbols: List[str], tick_handler: Callable):
    """
    Synchronous entry point to run multiple asynchronous WebSocket clients concurrently.
    This function should be run in a separate thread or process.
    """
    if not symbols:
        print("[WARNING] No symbols provided for ingestion.")
        return

    # Create a list of tasks for all symbols
    tasks = [connect_and_listen(sym, tick_handler) for sym in symbols]
    
    print(f"[Ingestion Manager] Starting collection for symbols: {', '.join(symbols)}")
    
    # 🛑 FIX: Explicitly set the event loop for this new thread
    try:
        # Create a new event loop
        loop = asyncio.new_event_loop()
        # Set it as the current event loop for this thread
        asyncio.set_event_loop(loop)
        
        # Run all tasks concurrently using the new loop
        loop.run_until_complete(asyncio.gather(*tasks))

    except KeyboardInterrupt:
        print("\n[Ingestion Manager] Stopped by user.")
    except Exception as e:
        print(f"[Ingestion Manager] Critical error in main loop: {e}")