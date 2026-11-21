import asyncio
import html
import os
import re
from time import monotonic
from urllib.parse import quote, urlparse

import httpx

SOURCES = ("Crossref", "OpenAlex", "Europe PMC")
_cache = {}


def clean(value):
    return " ".join(html.unescape(re.sub(r"<[^>]{1,200}>", "", str(value or ""))).split())


def link(value):
    try:
        return value if value and urlparse(value).scheme in ("https", "http") and urlparse(value).netloc else ""
    except ValueError:
        return ""


def record(title, authors, year, journal, doi, url, source):
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", (doi or "").strip(), flags=re.I).lower()
    if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
        doi = ""
    dest = "https://doi.org/" + quote(doi, safe="/:()") if doi else link(url)
    return {"title": clean(title), "authors": [clean(a) for a in authors if a][:16], "year": str(year or "")[:4],
            "journal": clean(journal), "doi": doi, "url": dest, "sources": [source]}


async def query(client, source, q, year):
    if source == "Crossref":
        params = {"query.bibliographic": q, "rows": 12}
        if year:
            params["filter"] = f"from-pub-date:{year}-01-01"
        if os.getenv("CROSSREF_MAILTO"):
            params["mailto"] = os.environ["CROSSREF_MAILTO"]
        r = await client.get("https://api.crossref.org/works", params=params)
        r.raise_for_status()
        rows = []
        for x in r.json()["message"]["items"]:
            authors = [" ".join(filter(None,(a.get("given"),a.get("family")))) or a.get("name") for a in x.get("author",[])]
            date = (x.get("issued") or {}).get("date-parts") or [[]]
            rows.append(record(next(iter(x.get("title",[])), ""), authors, next(iter(date[0]), ""),
                               next(iter(x.get("container-title",[])), ""), x.get("DOI"), x.get("URL"), source))
        return rows
    if source == "OpenAlex":
        params = {"search": q, "per_page": 12}
        if year:
            params["filter"] = f"from_publication_date:{year}-01-01"
        if os.getenv("OPENALEX_API_KEY"):
            params["api_key"] = os.environ["OPENALEX_API_KEY"]
        r = await client.get("https://api.openalex.org/works", params=params)
        r.raise_for_status()
        rows = []
        for x in r.json()["results"]:
            loc = x.get("primary_location") or {}
            authors = [(a.get("author") or {}).get("display_name") for a in x.get("authorships",[])]
            rows.append(record(x.get("display_name"), authors, x.get("publication_year"), (loc.get("source") or {}).get("display_name"),
                               x.get("doi"), loc.get("landing_page_url") or x.get("id"), source))
        return rows
    params = {"query": f"({q}) AND FIRST_PDATE:[{year}-01-01 TO 2999-12-31]" if year else q, "format":"json", "pageSize":12}
    r = await client.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params=params)
    r.raise_for_status()
    return [record(x.get("title"), (x.get("authorString") or "").rstrip(".").split(", "), x.get("pubYear"),
                   x.get("journalTitle"), x.get("doi"), "https://europepmc.org/abstract/" + quote(str(x["source"])) + "/" + quote(str(x["id"])), source)
            for x in r.json()["resultList"]["result"] if x.get("id") and x.get("source")]


def merge(groups):
    by_doi, by_title, results = {}, {}, []
    for row_number in range(max((len(rows) for rows in groups), default=0)):
        for rows in groups:
            if row_number >= len(rows):
                continue
            row = rows[row_number]
            if not row["title"]:
                continue
            title_key = (re.sub(r"[^\w]+","",row["title"].casefold()),row["year"])
            match = by_doi.get(row["doi"]) if row["doi"] else None
            if match is None:
                other = by_title.get(title_key)
                if other and (not row["doi"] or not other["doi"] or row["doi"] == other["doi"]):
                    match = other
            if match is None:
                match = row.copy()
                match["sources"] = row["sources"].copy()
                results.append(match)
            else:
                for source in row["sources"]:
                    if source not in match["sources"]:
                        match["sources"].append(source)
                if not match["doi"] and row["doi"]:
                    match.update(doi=row["doi"],url=row["url"])
            if match["doi"]:
                by_doi[match["doi"]] = match
            by_title[title_key] = match
    return results


async def search(q, source, year):
    key = (q.casefold(),source,year)
    cached = _cache.get(key)
    if cached and monotonic()-cached[0]<300:
        return cached[1]
    sources = SOURCES if source=="all" else (source,)
    async with httpx.AsyncClient(timeout=httpx.Timeout(15, connect=7),headers={"User-Agent":"Yanfolio/0.1 (academic literature search)"}) as client:
        replies = await asyncio.gather(*(query(client,s,q,year) for s in sources),return_exceptions=True)
    groups, status = [], {}
    for s, reply in zip(sources, replies):
        if isinstance(reply, Exception):
            status[s] = "请求受限，请稍后重试" if isinstance(reply,httpx.HTTPStatusError) and reply.response.status_code==429 else "数据源暂不可用"
        else:
            groups.append(reply)
            status[s] = f"返回 {len(reply)} 条"
    result = {"items": merge(groups), "status": status}
    if len(groups)==len(sources):
        if len(_cache)>=64:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (monotonic(),result)
    return result

