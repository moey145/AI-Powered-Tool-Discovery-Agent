import logging
import uuid
from contextvars import ContextVar
from typing import Optional
import time

# Request context tracking
request_id: ContextVar[str] = ContextVar('request_id', default='')
start_time: ContextVar[float] = ContextVar('start_time', default=0.0)

class RequestFormatter(logging.Formatter):
    """Custom formatter that includes request context"""
    
    def format(self, record):
        # Add request context to log record
        record.request_id = request_id.get()
        record.duration = time.time() - start_time.get() if start_time.get() > 0 else 0
        
        return super().format(record)

def setup_logger():
    """Setup structured logging with request tracking"""
    # Create logger
    logger = logging.getLogger('ai_research_agent')
    logger.setLevel(logging.INFO)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = RequestFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(request_id)s] - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with request context"""
    logger = logging.getLogger(f'ai_research_agent.{name}')
    return logger

def set_request_context(req_id: Optional[str] = None):
    """Set request context for logging"""
    if req_id is None:
        req_id = str(uuid.uuid4())[:8]
    
    request_id.set(req_id)
    start_time.set(time.time())
    
    return req_id

def log_request_start(query: str, logger: logging.Logger):
    """Log the start of a research request"""
    req_id = set_request_context()
    logger.info(f"🔍 Starting research request: {query}")
    return req_id

def log_request_complete(logger: logging.Logger, success: bool = True, error: Optional[str] = None):
    """Log the completion of a research request"""
    duration = time.time() - start_time.get()
    if success:
        logger.info(f"✅ Research request completed in {duration:.2f}s")
    else:
        logger.error(f"❌ Research request failed in {duration:.2f}s: {error}")
    
    # Clear context
    request_id.set('')
    start_time.set(0.0)
