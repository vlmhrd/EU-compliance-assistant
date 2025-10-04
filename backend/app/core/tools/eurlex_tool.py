# app/core/eurlex_tool.py

import httpx
from typing import Optional, Dict
from loguru import logger
from bs4 import BeautifulSoup


class EURLexTool:
    """Tool for fetching EU regulations by CELEX number from EUR-Lex"""
    
    name = "fetch_regulation_by_celex"
    description = """Fetch EU regulation by CELEX number from EUR-Lex. 
    Use this when user asks for specific EU regulations, directives, or legal documents.
    
    CELEX number format examples:
    - 32016R0679 (GDPR - Regulation 2016/679)
    - 32022L2464 (CSRD - Directive 2022/2464)
    - 32020R0852 (EU Taxonomy - Regulation 2020/852)
    
    Returns: Title, summary, and document metadata."""
    
    def __init__(self):
        self.base_url = "https://eur-lex.europa.eu/legal-content/EN/TXT/"
        self.timeout = 10.0
    
    async def fetch_regulation(self, celex_number: str) -> Dict[str, str]:
        """
        Fetch regulation by CELEX number.
        
        Args:
            celex_number: CELEX identifier (e.g., "32016R0679" for GDPR)
            
        Returns:
            Dictionary with regulation details
        """
        try:
            url = f"{self.base_url}?uri=CELEX:{celex_number}"
            
            logger.info(f"Fetching regulation from EUR-Lex: {celex_number}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract title
            title_elem = soup.find('h1', class_='title') or soup.find('title')
            title = title_elem.get_text(strip=True) if title_elem else "Title not found"
            
            # Extract document type and date
            doc_info = soup.find('div', class_='doc-ti')
            doc_type = doc_info.get_text(strip=True) if doc_info else "Unknown"
            
            # Extract summary or first paragraph
            summary_elem = soup.find('p', class_='sti-summary') or soup.find('p')
            summary = summary_elem.get_text(strip=True)[:500] if summary_elem else "Summary not available"
            
            result = {
                "celex_number": celex_number,
                "title": title,
                "document_type": doc_type,
                "summary": summary,
                "url": url,
                "status": "success"
            }
            
            logger.info(f"Successfully fetched regulation: {celex_number}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {celex_number}: {e}")
            return {
                "celex_number": celex_number,
                "error": f"Regulation not found (HTTP {e.response.status_code})",
                "status": "error",
                "url": url
            }
        except Exception as e:
            logger.error(f"Error fetching regulation {celex_number}: {e}")
            return {
                "celex_number": celex_number,
                "error": str(e),
                "status": "error"
            }
    
    async def search_regulations(
        self, 
        query: str, 
        year: Optional[int] = None,
        doc_type: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Search regulations by query text.
        
        Args:
            query: Search query
            year: Filter by year (e.g., 2016)
            doc_type: Filter by type ("regulation", "directive", "decision")
            
        Returns:
            Search results with CELEX numbers
        """
        try:
            # EUR-Lex search API endpoint
            search_url = "https://eur-lex.europa.eu/search.html"
            
            params = {
                "qid": "1234567890",  # Session identifier
                "text": query,
                "scope": "EURLEX",
                "type": "quick",
                "lang": "en"
            }
            
            if year:
                params["DD_YEAR"] = str(year)
            
            if doc_type:
                doc_type_map = {
                    "regulation": "32",
                    "directive": "31", 
                    "decision": "33"
                }
                params["DTS_DOM"] = doc_type_map.get(doc_type.lower(), "")
            
            logger.info(f"Searching EUR-Lex: {query}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(search_url, params=params)
                response.raise_for_status()
            
            # Parse search results
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract first few results
            results = []
            result_items = soup.find_all('div', class_='SearchResult')[:5]
            
            for item in result_items:
                title_elem = item.find('a', class_='title')
                celex_elem = item.find('span', class_='celex')
                
                if title_elem and celex_elem:
                    results.append({
                        "title": title_elem.get_text(strip=True),
                        "celex_number": celex_elem.get_text(strip=True),
                        "url": f"{self.base_url}?uri=CELEX:{celex_elem.get_text(strip=True)}"
                    })
            
            return {
                "query": query,
                "results_count": len(results),
                "results": results,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error searching regulations: {e}")
            return {
                "query": query,
                "error": str(e),
                "status": "error"
            }
    
    def run(self, celex_number: str) -> str:
        """
        Synchronous wrapper for LangChain tool compatibility.
        
        Args:
            celex_number: CELEX identifier
            
        Returns:
            Formatted string with regulation details
        """
        import asyncio
        
        result = asyncio.run(self.fetch_regulation(celex_number))
        
        if result["status"] == "success":
            return f"""
**{result['title']}**

Document Type: {result['document_type']}
CELEX: {result['celex_number']}

Summary: {result['summary']}

Full text: {result['url']}
"""
        else:
            return f"Error fetching regulation {celex_number}: {result.get('error', 'Unknown error')}"


# Global instance
eurlex_tool = EURLexTool()


# Common CELEX numbers for quick reference
COMMON_REGULATIONS = {
    "gdpr": "32016R0679",
    "csrd": "32022L2464", 
    "eu_taxonomy": "32020R0852",
    "dsa": "32022R2065",
    "dma": "32022R1925",
    "ai_act": "32024R1689",
    "nis2": "32022L2555"
}


def get_celex_by_name(regulation_name: str) -> Optional[str]:
    """Helper to get CELEX number by common name"""
    return COMMON_REGULATIONS.get(regulation_name.lower())