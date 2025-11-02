
# 🤖 AI Usage Transparency Note (`AI_USAGE.md`)

## Policy

In line with the assignment guidelines, AI tools (**Gemini / ChatGPT-4**) were utilized as technical assistants. Their primary role was to accelerate development, confirm syntax for new libraries, and aid in architectural verification, not to generate the core analytical reasoning or project architecture.

## Areas of AI Assistance

The following is a brief breakdown of where and how AI was utilized:

* **Architectural Guidance:** Structured the overall project components (Ingestion, API, Analytics, Frontend) to ensure alignment with the principles of **modularity** and **loose coupling**.
* **Boilerplate/Scaffolding:** Generated initial setup code for new libraries, including:
    * The asynchronous structure of the **`websockets`** client.
    * **SQLAlchemy** model definitions and basic session management.
    * **FastAPI** endpoint signatures and Pydantic request models.
* **Time-Series Debugging:** Assisted in resolving specific runtime errors related to complex library interactions, such as fixing the **`ValueError`** during **Pandas datetime parsing** (`ISO8601` format fix) and resolving the **`asyncio` event loop issue** when running the ingestion thread.
* **Documentation and Review:** Drafted the initial structure and content of the **`README.md`** to ensure all required deliverables and explanations were addressed clearly.

The final integration, analytical formulas (OLS, ADF test parameters), design choices (using FastAPI/Streamlit), and rationale for extensibility were driven by the developer.

***