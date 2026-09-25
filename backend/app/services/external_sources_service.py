"""External paper source ingestion service.

Fetches paper metadata + full text from arXiv, PubMed, Semantic Scholar, and
CORE (open-access hub), then ingests them through the same DocumentService
pipeline used for PDF uploads so they get chunked, embedded, and become
retrievable in RAG queries.
"""

import asyncio
import hashlib
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.user import User
from app.schemas.document import UploadResponse
from app.services.document_service import DocumentService

logger = get_logger(__name__)

# ── Shared HTTP timeouts ────────────────────────────────────────────────────
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


@dataclass
class PaperMetadata:
    title: str
    authors: str
    abstract: str
    source: str          # "arxiv" | "pubmed" | "semantic_scholar" | "core"
    external_id: str     # e.g. "2307.09288", "PMC1234", "CorpusID:12345", "CORE:12345"
    url: str
    published: str | None = None
    doi: str | None = None
    pdf_url: str | None = None  # direct PDF link when available


# ── arXiv ───────────────────────────────────────────────────────────────────

async def search_arxiv(query: str, max_results: int = 10) -> list[PaperMetadata]:
    """Search arXiv via the public Atom API."""
    base = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(base, params=params)
        resp.raise_for_status()
    return _parse_arxiv(resp.text)


def _parse_arxiv(xml_text: str) -> list[PaperMetadata]:
    """Parse Atom XML from arXiv into PaperMetadata objects."""
    import xml.etree.ElementTree as ET

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }
    root = ET.fromstring(xml_text)
    papers: list[PaperMetadata] = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        id_el = entry.find("atom:id", ns)
        published_el = entry.find("atom:published", ns)
        authors = [
            (a.find("atom:name", ns) or _empty()).text or ""
            for a in entry.findall("atom:author", ns)
        ]
        if title_el is None or id_el is None:
            continue
        arxiv_url = (id_el.text or "").strip()
        arxiv_id = arxiv_url.split("/abs/")[-1]
        papers.append(
            PaperMetadata(
                title=(title_el.text or "").strip().replace("\n", " "),
                authors=", ".join(a for a in authors if a),
                abstract=(summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else "",
                source="arxiv",
                external_id=arxiv_id,
                url=arxiv_url,
                published=(published_el.text or "")[:10] if published_el is not None else None,
            )
        )
    return papers


class _empty:
    text: str | None = None


# ── PubMed ──────────────────────────────────────────────────────────────────

async def search_pubmed(query: str, max_results: int = 10) -> list[PaperMetadata]:
    """Search PubMed via NCBI E-Utilities (no API key required for low-volume)."""
    base_search = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    base_fetch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        # 1. Get PMIDs
        search_resp = await client.get(base_search, params={
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
        })
        search_resp.raise_for_status()
        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        # 2. Fetch abstracts
        fetch_resp = await client.get(base_fetch, params={
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
            "rettype": "abstract",
        })
        fetch_resp.raise_for_status()
    return _parse_pubmed(fetch_resp.text)


def _parse_pubmed(xml_text: str) -> list[PaperMetadata]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml_text)
    papers: list[PaperMetadata] = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find("MedlineCitation")
        if medline is None:
            continue
        art = medline.find("Article")
        if art is None:
            continue

        title_el = art.find("ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else "Untitled"

        abstract_texts = art.findall(".//AbstractText")
        abstract = " ".join("".join(el.itertext()) for el in abstract_texts).strip()

        authors = []
        for a in art.findall(".//Author"):
            ln = a.find("LastName")
            fn = a.find("ForeName")
            if ln is not None:
                authors.append(f"{(ln.text or '')} {(fn.text or '')}".strip())

        pmid_el = medline.find("PMID")
        pmid = pmid_el.text if pmid_el is not None else "unknown"

        pub_date = medline.find(".//PubDate")
        published = None
        if pub_date is not None:
            year = pub_date.findtext("Year", "")
            month = pub_date.findtext("Month", "01")
            published = f"{year}-{month[:3]}" if year else None

        papers.append(PaperMetadata(
            title=title,
            authors=", ".join(authors),
            abstract=abstract,
            source="pubmed",
            external_id=pmid,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            published=published,
        ))
    return papers


# ── Semantic Scholar ─────────────────────────────────────────────────────────

async def search_semantic_scholar(query: str, max_results: int = 10) -> list[PaperMetadata]:
    """Search Semantic Scholar Graph API (public, no key for basic search)."""
    base = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,abstract,year,externalIds,url,openAccessPdf",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(base, params=params)
        resp.raise_for_status()
    data = resp.json().get("data", [])
    papers: list[PaperMetadata] = []
    for item in data:
        paper_id = item.get("paperId", "")
        external_ids = item.get("externalIds", {})
        doi = external_ids.get("DOI")
        authors = [a.get("name", "") for a in item.get("authors", [])]
        oa_pdf = item.get("openAccessPdf") or {}
        papers.append(PaperMetadata(
            title=item.get("title", "Untitled"),
            authors=", ".join(authors),
            abstract=item.get("abstract") or "",
            source="semantic_scholar",
            external_id=paper_id,
            url=item.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}",
            published=str(item["year"]) if item.get("year") else None,
            doi=doi,
            pdf_url=oa_pdf.get("url"),
        ))
    return papers


# ── CORE (open-access paper hub) ─────────────────────────────────────────────

async def search_core(query: str, max_results: int = 10) -> list[PaperMetadata]:
    """Search CORE (core.ac.uk) — a free open-access research paper aggregator.
    Uses the public CORE API v3 (no key required for basic queries).
    """
    base = "https://api.core.ac.uk/v3/search/works"
    payload = {
        "q": query,
        "limit": max_results,
        "fields": ["id", "title", "authors", "abstract", "yearPublished", "doi", "downloadUrl", "links"],
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(base, json=payload)
        resp.raise_for_status()
    results = resp.json().get("results", [])
    papers: list[PaperMetadata] = []
    for item in results:
        core_id = str(item.get("id", ""))
        authors_raw = item.get("authors") or []
        if isinstance(authors_raw, list):
            authors = ", ".join(
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in authors_raw
            )
        else:
            authors = str(authors_raw)
        doi = item.get("doi")
        download_url = item.get("downloadUrl")
        papers.append(PaperMetadata(
            title=(item.get("title") or "Untitled").strip(),
            authors=authors,
            abstract=(item.get("abstract") or "").strip(),
            source="core",
            external_id=core_id,
            url=f"https://core.ac.uk/works/{core_id}",
            published=str(item["yearPublished"]) if item.get("yearPublished") else None,
            doi=doi,
            pdf_url=download_url,
        ))
    return papers


# ── Orchestrator ────────────────────────────────────────────────────────────

class ExternalSourcesService:
    """Searches external APIs and ingests results through DocumentService."""

    def __init__(self, settings: Settings, document_service: DocumentService) -> None:
        self._settings = settings
        self._documents = document_service

    async def search(
        self,
        query: str,
        sources: list[str],
        max_per_source: int = 10,
    ) -> list[PaperMetadata]:
        """Return metadata from the requested sources without ingesting."""
        tasks: dict[str, Any] = {}
        if "arxiv" in sources:
            tasks["arxiv"] = search_arxiv(query, max_per_source)
        if "pubmed" in sources:
            tasks["pubmed"] = search_pubmed(query, max_per_source)
        if "semantic_scholar" in sources:
            tasks["semantic_scholar"] = search_semantic_scholar(query, max_per_source)
        if "core" in sources:
            tasks["core"] = search_core(query, max_per_source)

        results: list[PaperMetadata] = []
        settled = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for source, result in zip(tasks.keys(), settled):
            if isinstance(result, Exception):
                logger.warning("external_source_error", source=source, error=str(result))
            else:
                results.extend(result)  # type: ignore[arg-type]
        return results

    async def ingest(
        self,
        paper: PaperMetadata,
        user: User,
    ) -> UploadResponse:
        """Build a plain-text document from a PaperMetadata and push it
        through the normal DocumentService upload pipeline so it gets
        chunked, embedded, and indexed for RAG."""
        body = self._build_text(paper)
        filename = f"{paper.source}_{paper.external_id}.txt"
        content = body.encode("utf-8")

        return await self._documents.upload(
            user=user,
            filename=filename,
            content=content,
            title=paper.title,
            author=paper.authors or None,
            department=None,
            access_level="public",
            priority=0,
        )

    @staticmethod
    def _build_text(paper: PaperMetadata) -> str:
        parts = [
            f"Title: {paper.title}",
            f"Authors: {paper.authors}" if paper.authors else "",
            f"Published: {paper.published}" if paper.published else "",
            f"Source: {paper.source} | ID: {paper.external_id}",
            f"URL: {paper.url}",
            f"PDF: {paper.pdf_url}" if paper.pdf_url else "",
            f"DOI: {paper.doi}" if paper.doi else "",
            "",
            "Abstract:",
            paper.abstract or "(No abstract available)",
        ]
        return "\n".join(line for line in parts if line is not None)
