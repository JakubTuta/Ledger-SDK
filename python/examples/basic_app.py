import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from ledger import LedgerClient
from ledger.integrations.fastapi import LedgerMiddleware

env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[OK] Loaded configuration from {env_path}")
else:
    print(f"[WARNING] No .env file found at {env_path}")
    print("  Run: python scripts/setup_test_account.py")

api_key = os.getenv("LEDGER_API_KEY")
base_url = os.getenv("LEDGER_BASE_URL")

if not api_key:
    print("\n" + "=" * 60)
    print("ERROR: LEDGER_API_KEY not set!")
    print("=" * 60)
    print("\nPlease run the setup script first:")
    print("  python scripts/setup_test_account.py")
    print("\nOr set the environment variable manually:")
    print("  export LEDGER_API_KEY=your_api_key")
    print()
    sys.exit(1)

ledger = LedgerClient(
    api_key=api_key,
    base_url=base_url,
    flush_interval=5.0,
    max_buffer_size=10000,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    print("Shutting down, flushing remaining logs...")
    await ledger.shutdown(timeout=10.0)
    print("Shutdown complete")


app = FastAPI(title="Ledger SDK Example", lifespan=lifespan)

app.add_middleware(
    LedgerMiddleware,
    ledger_client=ledger,
    exclude_paths=["/health", "/metrics"],
)


@app.get("/")
async def root():
    return {"message": "Hello World", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/user/{user_id}")
async def get_user(user_id: int):
    ledger.log_info(f"Fetching user {user_id}", attributes={"user_id": user_id})

    if user_id == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"user_id": user_id, "name": f"User {user_id}"}


@app.post("/payment")
async def process_payment(amount: float):
    if amount < 0:
        raise ValueError("Amount must be positive")

    if amount > 10000:
        raise ValueError("Amount exceeds maximum limit")

    ledger.log_info(
        f"Payment processed: ${amount}",
        attributes={"amount": amount, "currency": "USD"},
    )

    return {"status": "success", "amount": amount}


@app.get("/error")
async def trigger_error():
    try:
        result = 1 / 0
    except Exception as e:
        ledger.log_exception(e, message="Division by zero error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics")
async def get_metrics():
    return ledger.get_metrics()


@app.get("/sdk/health")
async def sdk_health():
    return ledger.get_health_status()


if __name__ == "__main__":
    import uvicorn

    from ledger.core.config import DEFAULT_CONFIG

    print("\n" + "=" * 60)
    print("Ledger SDK Example App")
    print("=" * 60)
    print(f"Ledger Server:  {base_url or DEFAULT_CONFIG.base_url}")
    print(
        f"API Key:        {api_key[:20]}..." if len(api_key) > 20 else f"API Key:        {api_key}"
    )
    print(f"App URL:        http://localhost:8080")
    print(f"API Docs:       http://localhost:8080/docs")
    print("=" * 60)
    print("\nExample endpoints:")
    print("  GET  /              - Hello world")
    print("  GET  /user/123      - Get user (with logging)")
    print("  GET  /user/0        - Trigger 404 error")
    print('  POST /payment       - Process payment (with body: {"amount": 100})')
    print("  GET  /error         - Trigger exception")
    print("  GET  /metrics       - View SDK metrics")
    print("  GET  /health        - Health check (not logged)")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8080)
