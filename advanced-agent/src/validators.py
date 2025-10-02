import re
from typing import Optional
from pydantic import BaseModel, validator

class SearchQueryValidator(BaseModel):
    """Validate and sanitize search queries"""
    
    query: str
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        
        # Remove extra whitespace
        v = ' '.join(v.split())
        
        # Check minimum length
        if len(v) < 2:
            raise ValueError("Query must be at least 2 characters long")
        
        # Check maximum length
        if len(v) > 200:
            raise ValueError("Query must be less than 200 characters")
        
        # Check for potentially malicious content
        dangerous_patterns = [
            r'<script',
            r'javascript:',
            r'data:text/html',
            r'vbscript:',
            r'onload=',
            r'onerror=',
            r'<iframe',
            r'<object',
            r'<embed',
            r'<link',
            r'<meta',
            r'<style'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Query contains potentially dangerous content")
        
        # Check for SQL injection patterns
        sql_patterns = [
            r'union\s+select',
            r'drop\s+table',
            r'delete\s+from',
            r'insert\s+into',
            r'update\s+set',
            r';\s*drop',
            r';\s*delete',
            r';\s*insert',
            r';\s*update'
        ]
        
        for pattern in sql_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Query contains potentially dangerous SQL content")
        
        # Check for excessive special characters (potential spam/attack)
        special_char_count = len(re.findall(r'[^\w\s]', v))
        if special_char_count > len(v) * 0.3:  # More than 30% special characters
            raise ValueError("Query contains too many special characters")
        
        return v.strip()
    
    @validator('query')
    def sanitize_query(cls, v):
        """Remove or escape potentially problematic characters"""
        # Remove null bytes and control characters
        v = ''.join(char for char in v if ord(char) >= 32)
        
        # Escape HTML entities
        v = v.replace('&', '&amp;')
        v = v.replace('<', '&lt;')
        v = v.replace('>', '&gt;')
        v = v.replace('"', '&quot;')
        v = v.replace("'", '&#x27;')
        
        return v

def validate_search_query(query: str) -> tuple[bool, Optional[str]]:
    """Validate a search query and return (is_valid, error_message)"""
    try:
        SearchQueryValidator(query=query)
        return True, None
    except ValueError as e:
        return False, str(e)

def sanitize_query(query: str) -> str:
    """Basic query sanitization"""
    # Remove extra whitespace
    query = ' '.join(query.split())
    
    # Remove potentially dangerous characters
    query = re.sub(r'[<>"\']', '', query)
    
    # Limit length
    if len(query) > 200:
        query = query[:200]
    
    return query.strip()
