import os
import threading
import time
from datetime import datetime
import subprocess
import signal
import sys
import logging

os.makedirs('data', exist_ok=True)

# Set up basic logging (required for console output)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Import Core Modules ---
# NOTE: We only import these here for initialization purposes.
# The actual running API uses src.api.api_server
from src.ingestion.websocket_client import start_ingestion
from src.storage.db_manager import DBManager 
# The other modules (Resampler, PairsAnalyst) are imported within api_server.py

# --- Configuration ---
SYMBOLS = ["BTCUSDT", "ETHUSDT"] 
INGESTION_STARTUP_DELAY = 10 # Increased delay to allow more data for meaningful analysis/resampling
API_HOST = "127.0.0.1"
API_PORT = 8000
API_SERVER_PROCESS = None 

def start_ingestion_thread(db_manager: DBManager):
    """
    Sets up and starts the data ingestion process in a separate background thread.
    """
    logging.info("Initializing ingestion thread...")
    
    # Pass the DBManager's save_tick method as the callback handler
    tick_handler_callback = db_manager.save_tick
    
    ingestion_thread = threading.Thread(
        target=start_ingestion, 
        args=(SYMBOLS, tick_handler_callback),
        daemon=True 
    )
    ingestion_thread.start()
    
    logging.info(f"Real-time data ingestion started for: {', '.join(SYMBOLS)}")
    return ingestion_thread

def start_api_server():
    """
    Starts the FastAPI server using Uvicorn in a separate, non-blocking process.
    """
    global API_SERVER_PROCESS
    logging.info("Starting FastAPI server process...")
    
    # Command to run the Uvicorn server 
    command = [
        sys.executable, "-m", "uvicorn", 
        "src.api.api_server:app", 
        f"--host={API_HOST}", 
        f"--port={API_PORT}",
        "--log-level", "info"
    ]
    
    # We use subprocess.Popen to run the API in the background
    API_SERVER_PROCESS = subprocess.Popen(command)
    logging.info(f"FastAPI server running at http://{API_HOST}:{API_PORT}")
    time.sleep(3) # Give the server a moment to spin up
    
def shutdown_handler(signum, frame):
    """Gracefully shuts down the API server process and exits."""
    global API_SERVER_PROCESS
    logging.info("Shutting down gracefully...")
    
    if API_SERVER_PROCESS:
        logging.info("Terminating FastAPI server process...")
        API_SERVER_PROCESS.terminate()
        try:
            API_SERVER_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            API_SERVER_PROCESS.kill()
            
    logging.info("Cleanup complete. Exiting.")
    sys.exit(0)

def main():
    # Set up signal handling for graceful shutdown (Ctrl+C)
    signal.signal(signal.SIGINT, shutdown_handler)

    # 1. Setup Environment
    os.makedirs('data', exist_ok=True)
    
    # 2. Initialize Core Components (DBManager must run first to create the file)
    db_manager = DBManager()

    # 3. Start Data Ingestion (Phase 1)
    ingestion_thread = start_ingestion_thread(db_manager)

    # 4. Wait for initial data aggregation 
    # This delay ensures the SQLite DB has enough ticks for the first analysis query.
    logging.info(f"Waiting {INGESTION_STARTUP_DELAY} seconds for initial data accumulation...")
    time.sleep(INGESTION_STARTUP_DELAY)

    # 5. Start API Server (Phase 3)
    start_api_server()

    # 6. Keep the main thread alive 
    logging.info("\n--- System Fully Operational ---")
    print(f"Ingestion running, API live at http://{API_HOST}:{API_PORT}.")
    print("Open a SECOND terminal and run: 'streamlit run frontend/dashboard.py'")
    print("Press Ctrl+C in THIS terminal to exit the entire application.")
    
    # Loop to keep the main thread running until Ctrl+C is caught
    try:
        while True:
            time.sleep(1)
    except Exception:
        pass 

if __name__ == '__main__':
    # Check for required Uvicorn/FastAPI installation if necessary
    try:
        main()
    except Exception as e:
        print(f"Critical error during startup: {e}")
        sys.exit(1)