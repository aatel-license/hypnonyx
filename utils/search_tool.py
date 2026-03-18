#!/usr/bin/env python3
import sys
import json
import asyncio
from typing import List, Dict
from ddgs import DDGS

def search_duckduckgo(query: str, max_results: int = 3) -> List[Dict]:
    """Search using DuckDuckGo"""
    try:
        print(f"[DDG] Searching for: {query}", file=sys.stderr)
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            for r in results:
                r['source'] = 'DuckDuckGo'
            return results
    except Exception as e:
        print(f"[DDG] Error: {e}", file=sys.stderr)
        return []

def search_wikipedia(query: str, max_results: int = 2) -> List[Dict]:
    """Search using Wikipedia API"""
    try:
        import wikipedia
        print(f"[Wikipedia] Searching for: {query}", file=sys.stderr)
        
        # Search for pages
        search_results = wikipedia.search(query, results=max_results)
        results = []
        
        for title in search_results[:max_results]:
            try:
                page = wikipedia.page(title, auto_suggest=False)
                results.append({
                    'title': page.title,
                    'href': page.url,
                    'body': page.summary[:200],
                    'source': 'Wikipedia'
                })
            except:
                continue
                
        return results
    except ImportError:
        print("[Wikipedia] Library not installed (pip install wikipedia-api)", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[Wikipedia] Error: {e}", file=sys.stderr)
        return []

def search_stackoverflow(query: str, max_results: int = 2) -> List[Dict]:
    """Search StackOverflow using DuckDuckGo site-specific search"""
    try:
        print(f"[StackOverflow] Searching for: {query}", file=sys.stderr)
        
        # Use DuckDuckGo with site: operator
        stackoverflow_query = f"site:stackoverflow.com {query}"
        with DDGS() as ddgs:
            results = list(ddgs.text(stackoverflow_query, max_results=max_results))
            for r in results:
                r['source'] = 'StackOverflow'
            return results
    except Exception as e:
        print(f"[StackOverflow] Error: {e}", file=sys.stderr)
        return []

def deduplicate_results(results: List[Dict]) -> List[Dict]:
    """Remove duplicate URLs from results"""
    seen_urls = set()
    unique_results = []
    
    for result in results:
        url = result.get('href', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
    
    return unique_results

def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search using multiple providers and aggregate results.
    Returns a combined list from DuckDuckGo, Wikipedia, and StackOverflow.
    """
    all_results = []
    
    # Run searches sequentially
    ddg_results = search_duckduckgo(query, max_results=3)
    wiki_results = search_wikipedia(query, max_results=2)
    so_results = search_stackoverflow(query, max_results=2)
    
    # Combine results with priority: DDG, Wikipedia, StackOverflow
    all_results.extend(ddg_results)
    all_results.extend(wiki_results)
    all_results.extend(so_results)
    
    # Deduplicate
    unique_results = deduplicate_results(all_results)
    
    # Limit to max_results
    return unique_results[:max_results]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No query provided"}))
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    results = search_web(query, max_results=5)
    print(json.dumps(results, indent=2))
