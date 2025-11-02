
# 🚀 Quant Developer Analytical App

## Real-Time Pairs Trading & Market Analytics Dashboard

This project is a small, complete analytical application designed to ingest real-time tick data, perform quantitative analysis (specifically pairs trading metrics), and present the results through an interactive, near real-time dashboard. The architecture prioritizes **modularity**, **loose coupling**, and **extensibility**.

-----

## 🛠️ 1. Setup and Installation

### A. Environment Setup

The application requires Python 3.9+ and uses a virtual environment for dependency management.

1.  **Clone the repository (or extract the project files).**
2.  **Create and activate the virtual environment:**
    ```bash
    python3 -m venv quant_dev_env
    source quant_dev_env/bin/activate  # macOS/Linux
    # quant_dev_env\Scripts\activate.bat # Windows
    ```

### B. Dependency Installation

Install all required libraries, including the backend, analytics, and frontend components, using the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

-----

## ▶️ 2. Execution

The system must be run in two separate terminals to start the asynchronous background services and the interactive frontend.

### Step 1: Launch Backend Services (Terminal 1)

This command executes `app.py`, which is the entry point for all background tasks:

1.  Starts the **Asynchronous Data Ingestion Thread** (Binance WebSockets for BTCUSDT/ETHUSDT).
2.  Initializes **SQLite Storage** and begins persisting raw tick data.
3.  Launches the **FastAPI Server** (Uvicorn) to host analytical and live stats API endpoints.

<!-- end list -->

```bash
python app.py
```

> **Wait for the console output to confirm the FastAPI server is running (e.g., `Uvicorn running on http://127.0.0.1:8000`) and the initial data accumulation delay has passed.**

### Step 2: Launch Frontend Dashboard (Terminal 2)

Open a **second terminal** with the virtual environment activated, and run the Streamlit script to launch the UI:

```bash
streamlit run frontend/dashboard.py
```

> The browser will automatically open the interactive dashboard. You can now use the sidebar controls and click "Run Full Analysis" to generate the charts.

-----

## 🧠 3. Methodology and Analytics Explanation

### A. Core Workflow

The architecture follows a clear pipeline:

1.  **Data Ingestion (`src/ingestion`):** Raw ticks (price, size, timestamp) are streamed and saved to the SQLite database.
2.  **Data Retrieval & Resampling (`src/analytics/resampling`):** On demand, data is retrieved from the DB and converted into synchronous **OHLCV bars** for selectable timeframes (1min, 5min, etc.) using Pandas.
3.  **Analytics (`src/analytics/pairs_trading`):** Core pairs trading models run on the resampled data.
4.  **API Service (`src/api`):** FastAPI exposes the computed time series data (Spread, Z-score) and metadata (Hedge Ratio, ADF results) to the frontend.

### B. Key Quantitative Metrics

| Metric | Calculation / Purpose | Tooling |
| :--- | :--- | :--- |
| **Hedge Ratio ($\beta$)** | Calculated via **OLS Regression** on the **logarithm of prices** (log prices stabilize the relationship). | `statsmodels` |
| **Spread** | The residual from the OLS model: $\text{Spread} = \log(\text{Price}_Y) - (\alpha + \beta \cdot \log(\text{Price}_X))$. This is the component expected to mean-revert.. | `numpy`, `pandas` |
| **Z-Score** | $Z = (\text{Spread} - \mu_{roll}) / \sigma_{roll}$. Tracks how many rolling standard deviations the current spread is from its rolling mean. **Used for generating trading signals.**. | `pandas` |
| **ADF Test** | **Augmented Dickey-Fuller Test** on the Spread. A p-value $\le 0.05$ is required to prove the Spread is **stationary** and therefore tradable. | `statsmodels` |

### C. Near Real-Time Features

  * **Live Metrics:** The dashboard polls the `/api/v1/live_stats` endpoint frequently to display the latest Z-score and current prices, achieving **near-real-time updates** without re-running the heavy historical analysis.
  * **Alerting:** Rule-based logic triggers a visible notification when the latest Z-score exceeds the user-defined $\pm 2.0$ threshold.
  * **Data Export:** A button allows users to download the final processed time-series data (Spread, Z-score, Correlation) as a CSV file.

-----

## 📐 4. Architecture and Extensibility

The architecture is explicitly designed to minimize rework if components change:

  * **Decoupling:** The **Analytics** module (`PairsAnalyst`) relies only on the abstract data retrieval methods provided by the `Resampler` and `DBManager`. It does not know or care if the data came from a WebSocket or an uploaded CSV.
  * **Extensibility:** Adding a new analytic (e.g., Kalman Filter) only requires creating a new Python module and adding a corresponding FastAPI endpoint, making the system easy to grow without breaking existing logic.
  * **Delivery:** The entire system is built on Python, but the FastAPI layer could easily be replaced with a robust messaging queue (like Kafka) if the visualization was a separate, non-Python service.

