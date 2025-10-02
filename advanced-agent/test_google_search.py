#!/usr/bin/env python3
"""
Test script for Google Custom Search API integration
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Add src to path
sys.path.append('.')

from src.search_providers import GoogleCustomSearchProvider, SearchManager
from src.config import settings

async def test_google_search():
    """Test the Google Custom Search provider"""
    print("🔍 Testing Google Custom Search Integration")
    print("=" * 50)
    
    # Check configuration
    print(f"Google Custom Search API Key: {'✅ Set' if settings.google_custom_search_api_key else '❌ Not Set'}")
    print(f"Google Search Engine ID: {'✅ Set' if settings.google_search_engine_id else '❌ Not Set'}")
    print(f"Search Provider: {settings.search_provider}")
    print()
    
    # Test provider availability
    provider = GoogleCustomSearchProvider()
    print(f"Provider Available: {'✅ Yes' if provider.is_available() else '❌ No'}")
    
    if not provider.is_available():
        print("\n❌ Google Custom Search provider not available!")
        print("Please check your .env file configuration.")
        return
    
    # Test search manager
    print("\n🔍 Testing Search Manager...")
    search_manager = SearchManager()
    
    print(f"Available Providers: {search_manager.get_available_providers()}")
    print(f"Provider Order: {search_manager.provider_order}")
    
    # Test a simple search
    print("\n🔍 Testing Search Query: 'Python web frameworks'")
    try:
        results = await search_manager.search("Python web frameworks", 5)
        
        if results.get("data"):
            print(f"✅ Search successful! Found {len(results['data'])} results")
            print("\n📋 Results:")
            for i, result in enumerate(results['data'][:3], 1):
                print(f"\n{i}. {result['title']}")
                print(f"   URL: {result['url']}")
                print(f"   Source: {result['metadata'].get('source', 'Unknown')}")
                print(f"   Snippet: {result['snippet'][:100]}...")
        else:
            print("❌ No results found")
            
    except Exception as e:
        print(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function"""
    # Load environment variables
    load_dotenv()
    
    # Run async test
    asyncio.run(test_google_search())

if __name__ == "__main__":
    main()
