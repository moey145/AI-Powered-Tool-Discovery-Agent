#!/usr/bin/env python3
"""
Test script to demonstrate the validation functionality
"""

from src.validators import validate_search_query, sanitize_query

def test_validation():
    """Test various validation scenarios"""
    
    test_cases = [
        # Valid queries
        ("JavaScript testing frameworks", True, "Valid query"),
        ("Python web frameworks", True, "Valid query"),
        ("React state management tools", True, "Valid query"),
        ("a", True, "Minimum length query"),
        
        # Invalid queries
        ("", False, "Empty query"),
        (" ", False, "Whitespace only"),
        ("a", False, "Too short (1 character)"),
        ("x" * 201, False, "Too long (201 characters)"),
        
        # Dangerous content
        ("<script>alert('xss')</script>", False, "XSS attempt"),
        ("javascript:alert('xss')", False, "JavaScript protocol"),
        ("<iframe src='evil.com'>", False, "Iframe injection"),
        ("<object data='evil.swf'>", False, "Object injection"),
        
        # SQL injection attempts
        ("'; DROP TABLE users; --", False, "SQL injection"),
        ("' UNION SELECT * FROM users", False, "SQL UNION attack"),
        ("'; DELETE FROM users; --", False, "SQL DELETE attack"),
        
        # Excessive special characters
        ("!@#$%^&*()!@#$%^&*()!@#$%^&*()", False, "Too many special chars"),
        
        # Edge cases
        ("JavaScript testing frameworks!!!", True, "Valid with some special chars"),
        ("Python & Django frameworks", True, "Valid with ampersand"),
    ]
    
    print("🧪 Testing Search Query Validation")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for query, expected_valid, description in test_cases:
        is_valid, error_msg = validate_search_query(query)
        
        if is_valid == expected_valid:
            status = "✅ PASS"
            passed += 1
        else:
            status = "❌ FAIL"
            failed += 1
        
        print(f"{status} | {description}")
        print(f"    Query: '{query[:50]}{'...' if len(query) > 50 else ''}'")
        print(f"    Expected: {'Valid' if expected_valid else 'Invalid'}")
        print(f"    Got: {'Valid' if is_valid else f'Invalid - {error_msg}'}")
        print()
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed!")

def test_sanitization():
    """Test query sanitization"""
    
    print("\n🧹 Testing Query Sanitization")
    print("=" * 50)
    
    test_queries = [
        "  JavaScript   testing   frameworks  ",
        "Python & Django frameworks",
        "React <state> management",
        "Vue.js 'testing' tools",
        "Angular \"framework\" libraries",
    ]
    
    for query in test_queries:
        sanitized = sanitize_query(query)
        print(f"Original:  '{query}'")
        print(f"Sanitized: '{sanitized}'")
        print()

if __name__ == "__main__":
    test_validation()
    test_sanitization()
