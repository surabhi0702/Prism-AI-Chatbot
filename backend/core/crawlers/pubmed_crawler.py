"""PRISM — PubMed & CDC Crawlers"""
import asyncio, time
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from backend.config.settings import get_settings

settings = get_settings()
PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CDC_BASE    = "https://www.cdc.gov"


class PubMedCrawler:
    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        params = {"db":"pubmed","term":query,"retmax":max_results,"retmode":"json",
                  "email":settings.pubmed_email,"tool":"PRISM"}
        if settings.ncbi_api_key:
            params["api_key"] = settings.ncbi_api_key
        try:
            r = requests.get(f"{PUBMED_BASE}/esearch.fcgi", params=params, timeout=15)
            ids = r.json().get("esearchresult", {}).get("idlist", [])
            return self._fetch_abstracts(ids)
        except Exception as e:
            print(f"[PubMed] Search Error: {e}")
            return []

    def _fetch_abstracts(self, pmids: List[str]) -> List[Dict]:
        if not pmids: return []
        ids_str = ",".join(pmids)
        params = {"db":"pubmed","id":ids_str,"retmode":"xml","rettype":"abstract",
                  "email":settings.pubmed_email}
        if settings.ncbi_api_key:
            params["api_key"] = settings.ncbi_api_key
        try:
            r = requests.get(f"{PUBMED_BASE}/efetch.fcgi", params=params, timeout=20)
            soup = BeautifulSoup(r.content, "xml")
            articles = []
            for art in soup.find_all("PubmedArticle"):
                pmid_el  = art.find("PMID")
                title_el = art.find("ArticleTitle")
                abs_el   = art.find("AbstractText")
                year_el  = art.find("Year")
                journal  = art.find("Title")
                articles.append({
                    "pmid":    pmid_el.text if pmid_el else "",
                    "title":   title_el.text if title_el else "Untitled",
                    "abstract": abs_el.text if abs_el else "",
                    "year":    int(year_el.text) if year_el else None,
                    "journal": journal.text if journal else "",
                    "source":  f"PubMed PMID:{pmid_el.text}" if pmid_el else "PubMed",
                    "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid_el.text}/" if pmid_el else "",
                    "doc_type": "pubmed_abstract",
                })
            return articles
        except Exception as e:
            print(f"[PubMed] Fetch Error: {e}")
            return []


class CDCCrawler:
    CDC_TOPICS = {
        "CA": "/cancer/", "DM": "/diabetes/", "CV": "/heartdisease/",
        "MH": "/mentalhealth/", "RS": "/niosh/topics/respiratory/",
    }

    def crawl(self, disease_code: str, max_pages: int = 5) -> List[Dict]:
        path = self.CDC_TOPICS.get(disease_code, "/")
        url  = CDC_BASE + path
        docs = []
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "PRISM/2.0 Academic"})
            soup = BeautifulSoup(r.content, "html.parser")
            # Grab main content
            main = soup.find("main") or soup.find("div", class_="content") or soup
            text = main.get_text(separator=" ", strip=True)
            title = soup.find("h1")
            docs.append({
                "title":    title.text.strip() if title else f"CDC {disease_code}",
                "text":     text[:5000],
                "source":   "CDC",
                "source_url": url,
                "doc_type": "cdc_web",
                "year":     2024,
            })
            # Follow internal links
            links = [a["href"] for a in soup.find_all("a", href=True)
                     if a["href"].startswith(path)][:max_pages-1]
            for link in links:
                time.sleep(0.5)
                try:
                    rp = requests.get(CDC_BASE + link, timeout=10,
                                      headers={"User-Agent":"PRISM/2.0"})
                    sp = BeautifulSoup(rp.content, "html.parser")
                    mn = sp.find("main") or sp
                    tx = mn.get_text(separator=" ", strip=True)
                    h1 = sp.find("h1")
                    docs.append({
                        "title": h1.text.strip() if h1 else link,
                        "text":  tx[:5000],
                        "source": "CDC",
                        "source_url": CDC_BASE + link,
                        "doc_type": "cdc_web",
                        "year": 2024,
                    })
                except Exception:
                    continue
        except Exception:
            pass
        return docs
