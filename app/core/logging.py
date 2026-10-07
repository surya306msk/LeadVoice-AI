import logging
import sys

def mask_secret(secret: str) -> str:
    """Mask secret tokens or keys in log messages."""
    if not secret:
        return "[EMPTY]"
    if len(secret) <= 8:
        return "****"
    return f"{secret[:3]}****{secret[-4:]}"

def mask_phone(phone: str) -> str:
    """Mask phone numbers for log privacy."""
    if not phone:
        return "[EMPTY]"
    clean = phone.strip()
    if len(clean) <= 5:
        return "****"
    return f"{clean[:3]}****{clean[-3:]}"

def setup_logging():
    log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    logger = logging.getLogger("leadvoice")
    logger.info("Logging system initialized with secret & phone privacy masking.")
    return logger

logger = setup_logging()
