# web_tools.py

from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_core.tools import tool
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from ddgs import DDGS
import html

def _scrape_url(url: str) -> str:
    """Helper function to scrape text from a single webpage."""
    if not url: return ""
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=3.5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.extract()
            text = soup.get_text(separator=' ', strip=True)
            return f"Source URL: {url}\nContent: {text[:1500]}"
    except Exception as e:
        print(f"⚠️ [Scraper] Skipping {url}: {e}")
    return ""

@tool
def web_search_tool(query: str) -> str:
    """Useful for searching the internet for recent events, facts, live market/finance data (like gold or stock prices), schedules, and detailed lists. Automatically scrapes full webpages.
    Always prioritize providing the direct Source URLs found in the results to the user."""
    try:
        wrapper = DuckDuckGoSearchAPIWrapper()
        search_results = wrapper.results(query, max_results=5)
        
        if not search_results:
            print(f"⚠️ [Web Search] No results found for query: '{query}'")
            return "No results found on the web."
            
        urls_to_scrape = [res.get('link') for res in search_results if res.get('link')]
        
        print(f"🔗 [Web Search] DuckDuckGo found {len(urls_to_scrape)} links. Scraping data from:")
        for u in urls_to_scrape:
            print(f"   -> {u}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(_scrape_url, urls_to_scrape)
            scraped_data = [res for res in results if res]
            
        if not scraped_data:
            return "\n\n".join([f"Source URL: {res.get('link')}\nSnippet: {res.get('snippet', '')}" for res in search_results])
            
        return "\n\n".join(scraped_data)
    except Exception as e:
        print(f"❌ [Web Search] Failed: {e}")
        return "Web search is currently unavailable or rate-limited. Please rely on your internal knowledge or conversation history."

@tool
def product_search_tool(query: str) -> str:
    """Searches for products, specific brands, gadgets, or items to buy. Returns product details, prices, and a thumbnail image.
    Always use this tool first when the user is looking to buy something, find the best price, compare products, or asks for specific brands.
    If the user asks for a specific website  append 'site:amazon.in' or 'site:flipkart.com' to your query to ensure accurate links."""
    try:
        wrapper = DuckDuckGoSearchAPIWrapper()
        results = wrapper.results(query, max_results=5)
        
        if results:
            print(f"🛍️ [Product Search] DuckDuckGo found {len(results)} products for '{query}':")
            for r in results:
                print(f"   -> {r.get('title')} | {r.get('link')}")
        
        image_url = ""
        if results:
            top_title = results[0].get("title", query)
            clean_title = top_title.split('|')[0].split('-')[0].strip()
            
            try:
                with DDGS() as ddgs:
                    img_results = list(ddgs.images(f"{clean_title} official product", max_results=1))
                    if img_results:
                        image_url = img_results[0].get("image", "")
            except Exception as img_e:
                print(f"⚠️ [Image Search] Failed: {img_e}")
        
        if not results:
            return "No products found."
        
        response = f"PRODUCT QUERY: {query}\n\n"
        if image_url:
            response += f"VERIFIED IMAGE URL: {image_url}\n(Embed this exactly as !Product Image at the top of your response)\n\n"
        else:
            response += "VERIFIED IMAGE URL: [NONE]. DO NOT include any image markdown. DO NOT hallucinate fake image links.\n\n"
        
        response += "WEB SEARCH RESULTS (Extract name, price, description, and link from here):\n"
        for res in results:
            response += f"- Title: {res.get('title')}\n  Snippet: {res.get('snippet')}\n  Link: {res.get('link')}\n\n"
        
        response += "CRITICAL INSTRUCTION: Format your final answer to the user as a clean Markdown list or table. Include the Image (if provided) at the top using Markdown. You MUST include ALL the products listed above. For the link, DO NOT use markdown syntax like [Buy Now](link) because complex URLs will break. Instead, you MUST use raw HTML for the links exactly like this: <a href=\"EXACT_LINK\" target=\"_blank\" style=\"color: #10a37f; text-decoration: none;\"><b>🛒 View / Buy Now</b></a>."
        return response
    except Exception as e:
        return f"Failed to fetch product details: {e}"
