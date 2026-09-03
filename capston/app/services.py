import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_geo_data(ip_address: str) -> dict:
    """
    Fallback chain for IP Geolocation:
    Provider A (ip-api.com) -> Provider B (ipapi.co) -> Graceful degradation
    """
    if not ip_address or ip_address in ("127.0.0.1", "localhost", "::1"):
        return {"country": "Localhost", "city": "Localhost"}

    # Provider A
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"http://ip-api.com/json/{ip_address}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    logger.info("Geo enrichment resolved via Provider A (ip-api.com)")
                    return {"country": data.get("country"), "city": data.get("city")}
    except Exception as e:
        logger.warning(f"Geo Provider A failed: {e}. Falling back to Provider B.")

    # Provider B
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"https://ipapi.co/{ip_address}/json/")
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("error"):
                    logger.info("Geo enrichment resolved via Provider B (ipapi.co)")
                    return {"country": data.get("country_name"), "city": data.get("city")}
    except Exception as e:
        logger.warning(f"Geo Provider B failed: {e}. Degrading gracefully.")

    # Total failure fallback: system stays up, returns empty geo data
    return {"country": None, "city": None}

def send_confirmation_email_side_effect(email: str, submission_id: str):
    """
    Secondary side-effect operation. Failure must never interrupt main submission process.
    """
    try:
        # Simulate secondary operations (SMTP/Webhook)
        logger.info(f"Triggering confirmation side-effect for {email} (Submission: {submission_id})")
        # Uncommenting below line tests side-effect failure resilience:
        # raise Exception("SMTP Server Connection Timeout")
    except Exception as err:
        logger.error(f"Non-critical side-effect error caught safely: {err}")