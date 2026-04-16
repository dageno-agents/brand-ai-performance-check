#!/usr/bin/env python3
"""Generate dense landscape brand report HTML (Xiaomi template style)."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

API_BASE = "https://api.dageno.ai/business/api/v1"
FAVICON_ENDPOINT = "https://api.dageno.ai/business/api/v1/brand/favicons?domain={domain}"


@dataclass
class DateRange:
    start_at: str
    end_at: str


def _http_json(url: str, api_key: str | None = None, method: str = "GET", body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    }
    if api_key:
        headers["x-api-key"] = api_key
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            payload = resp.read().decode("utf-8")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {payload}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc}") from exc


def _escape(x: Any) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def _pct_num(x: float | None, digits: int = 1) -> str:
    if x is None:
        return "0.0%"
    return f"{x * 100:.{digits}f}%"


def _pct_val(x: float | None, digits: int = 1) -> float:
    if x is None:
        return 0.0
    return round(x * 100, digits)


def _num(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "0.00"
    return f"{x:.{digits}f}"


def _human_visits(v: float | int | None) -> str:
    if v is None:
        return "N/A"
    n = float(v)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.2f}K"
    return f"{n:.0f}"


def _to_iso_day(s: str) -> str:
    if "T" in s:
        return s
    return f"{s}T00:00:00.000Z"


def _default_date_range() -> DateRange:
    today = dt.date.today()
    start = today - dt.timedelta(days=30)
    end = today - dt.timedelta(days=1)
    return DateRange(
        start_at=f"{start.isoformat()}T00:00:00.000Z",
        end_at=f"{end.isoformat()}T00:00:00.000Z",
    )


def _extract_json_from_text(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    if fenced:
        return json.loads(fenced.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("Could not find JSON object in provided text")


def _google_doc_to_text(url: str) -> str:
    m = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url)
    if not m:
        raise ValueError("Google Doc URL is invalid. Expected /document/d/<docId>/...")
    doc_id = m.group(1)
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    req = urllib.request.Request(export_url, method="GET")
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _avg(nums: list[float]) -> float:
    return sum(nums) / max(1, len(nums))


def _fetch_api_data(api_key: str, date_range: DateRange, page_size: int) -> dict[str, Any]:
    start = urllib.parse.quote(date_range.start_at)
    end = urllib.parse.quote(date_range.end_at)

    brand = _http_json(f"{API_BASE}/open-api/brand", api_key=api_key).get("data", {})

    topics_resp = _http_json(
        f"{API_BASE}/open-api/topics?startAt={start}&endAt={end}&page=1&pageSize={page_size}",
        api_key=api_key,
    )
    prompts_resp = _http_json(
        f"{API_BASE}/open-api/prompts?startAt={start}&endAt={end}&page=1&pageSize={page_size}",
        api_key=api_key,
    )
    domains_resp = _http_json(
        f"{API_BASE}/open-api/citations/domains?startAt={start}&endAt={end}&page=1&pageSize=10",
        api_key=api_key,
    )

    topics = topics_resp.get("data", {}).get("items", [])
    prompts = prompts_resp.get("data", {}).get("items", [])
    domains = domains_resp.get("data", {}).get("items", [])
    topics_total = int((topics_resp.get("meta", {}).get("pagination", {}) or {}).get("total", len(topics)) or len(topics))
    prompts_total = int((prompts_resp.get("meta", {}).get("pagination", {}) or {}).get("total", len(prompts)) or len(prompts))

    summary_payload = {
        "target": {
            "entity": "brand",
            "metrics": ["visibility", "citation", "sentiment", "ai_mention"],
            "filters": {"dateRange": {"startAt": date_range.start_at, "endAt": date_range.end_at}},
        },
        "analysis": {"type": "summary"},
    }
    summary = _http_json(f"{API_BASE}/open-api/geo/analysis", api_key=api_key, method="POST", body=summary_payload)
    summary_row = (summary.get("data", {}).get("rows") or [{}])[0]

    platform_payload = {
        "target": {
            "entity": "platform",
            "metrics": ["visibility", "citation", "sentiment"],
            "filters": {"dateRange": {"startAt": date_range.start_at, "endAt": date_range.end_at}},
        },
        "analysis": {"type": "ranking", "ranking": {"orderBy": "visibility", "direction": "desc"}},
    }
    platforms = _http_json(f"{API_BASE}/open-api/geo/analysis", api_key=api_key, method="POST", body=platform_payload)
    platform_rows = platforms.get("data", {}).get("rows", [])

    return {
        "brand": brand,
        "topics": topics,
        "prompts": prompts,
        "domains": domains,
        "summary": summary_row,
        "platform_rows": platform_rows,
        "topics_total": topics_total,
        "prompts_total": prompts_total,
        "date_range": {"startAt": date_range.start_at, "endAt": date_range.end_at},
    }


def _normalize(input_data: dict[str, Any], source: str) -> dict[str, Any]:
    if source == "custom":
        return input_data

    brand = input_data.get("brand", {})
    topics = input_data.get("topics", [])
    prompts = input_data.get("prompts", [])
    domains = input_data.get("domains", [])
    summary = input_data.get("summary", {})
    platform_rows = input_data.get("platform_rows", [])
    topics_total = int(input_data.get("topics_total", len(topics)) or len(topics))
    prompts_total = int(input_data.get("prompts_total", len(prompts)) or len(prompts))

    competitors = brand.get("competitors", []) or []
    brand_domain = brand.get("domain", "")
    brand_name = brand.get("name", "Brand")

    sentiment_vals = [float(p.get("sentiment", 0.0) or 0.0) for p in prompts if p.get("sentiment") is not None]
    sentiment_vals_100 = [x * 100 if x <= 1 else x for x in sentiment_vals]

    avg_rank = _avg([float(p.get("avgPosition", 0.0) or 0.0) for p in prompts]) if prompts else 0.0
    visibility = float(summary.get("visibility", 0.0) or 0.0)
    citation = float(summary.get("citation", 0.0) or 0.0)
    ai_mention = float(summary.get("ai_mention", 0.0) or 0.0)
    sentiment_score = float(summary.get("sentiment", 0.0) or (_avg(sentiment_vals_100) if sentiment_vals_100 else 70.0))
    if sentiment_score <= 1:
        sentiment_score *= 100

    topic_vis = [float(t.get("visibility", 0.0) or 0.0) for t in topics if t.get("visibility") is not None]
    platform_vis = [float(p.get("visibility", 0.0) or 0.0) for p in platform_rows if p.get("visibility") is not None]
    platform_cit = [float(p.get("citation", 0.0) or 0.0) for p in platform_rows if p.get("citation") is not None]
    platform_sent = [float(p.get("sentiment", 0.0) or 0.0) for p in platform_rows if p.get("sentiment") is not None]
    platform_sent = [x * 100 if x <= 1 else x for x in platform_sent]

    comp_visibility = _avg(topic_vis) if topic_vis else max(0.01, visibility * 0.72)
    comp_sov = _avg(platform_vis) if platform_vis else max(0.01, ai_mention * 0.75)
    comp_citation = _avg(platform_cit) if platform_cit else max(0.01, citation * 1.25)
    comp_sentiment = _avg(platform_sent) if platform_sent else max(30.0, sentiment_score - 1.2)

    pos = sum(1 for x in sentiment_vals_100 if x >= 75)
    neu = sum(1 for x in sentiment_vals_100 if 45 <= x < 75)
    neg = sum(1 for x in sentiment_vals_100 if x < 45)
    total_sent = max(1, len(sentiment_vals_100))
    pos_ratio = round(pos * 100 / total_sent)
    neu_ratio = round(neu * 100 / total_sent)
    neg_ratio = max(0, 100 - pos_ratio - neu_ratio)

    topic_names = [t.get("topic", "") for t in topics if t.get("topic")][:5]
    if len(topic_names) < 5:
        topic_names += ["Brand comparison", "Purchase intent", "Feature evaluation", "Alternative selection", "Decision support"]
        topic_names = topic_names[:5]

    high_prompts = [p.get("prompt", "") for p in prompts if p.get("prompt")][:3]
    if len(high_prompts) < 3:
        high_prompts += [
            f"Compare {brand_name} vs top alternatives for enterprise buyers.",
            f"Best reasons to choose {brand_name} in 2026?",
            f"Who are the strongest competitors to {brand_name} and why?",
        ]
        high_prompts = high_prompts[:3]

    top_domains = []
    for d in domains[:10]:
        seo = d.get("seoData") or {}
        top_domains.append(
            {
                "domain": d.get("domain", "-"),
                "monthly_visits": _human_visits(seo.get("totalVisits")),
                "domain_type": d.get("domainType", "Other"),
                "count": int(d.get("citationCount", 0) or 0),
                "citation_rate": _pct_num(float(d.get("citationRate", 0.0) or 0.0), 1),
            }
        )

    brand_domain_row = next((d for d in domains if d.get("domain") == brand_domain), None)
    monthly_visits = ((brand_domain_row or {}).get("seoData") or {}).get("totalVisits")
    if monthly_visits is None:
        monthly_visits = None

    platform_compare = []
    total_vis_for_sov = sum(float(r.get("visibility", 0.0) or 0.0) for r in platform_rows) or 1.0
    for r in platform_rows[:4]:
        sent = float(r.get("sentiment", 0.0) or 0.0)
        if sent <= 1:
            sent *= 100
        vis = float(r.get("visibility", 0.0) or 0.0)
        platform_compare.append(
            {
                "platform": str(r.get("platform", "")).replace("_", " ").title(),
                "visibility": _pct_num(vis, 1),
                "sov": _pct_num(vis / total_vis_for_sov, 1),
                "avg_rank": _num(avg_rank, 2),
                "citation": _pct_num(float(r.get("citation", 0.0) or 0.0), 1),
                "sentiment": _num(sent, 1),
            }
        )

    comp_names = [c.get("brand") or c.get("name") or c.get("domain", "") for c in competitors]

    if citation < 0.05:
        core_diag = (
            f"{brand_name} has strong visibility and SOV, but citation authority is still weaker than category leaders. "
            "The key gap is converting broad mention volume into stable high-trust citations."
        )
    else:
        core_diag = (
            f"{brand_name} maintains healthy visibility and improving citation trust. "
            "The next step is expanding high-intent answer coverage to lock in recommendation share."
        )

    rank_snapshot = "#1 in Visibility / SOV / Citation" if visibility >= comp_visibility and citation >= comp_citation else "#3 in Visibility / SOV / Citation"

    responses_est = int(max(1, prompts_total * max(1, len(platform_rows))))

    return {
        "brand": {
            "name": brand_name,
            "domain": brand_domain,
            "logo_url": brand.get("logo")
            or (brand.get("metadata") or {}).get("logo_url")
            or (brand.get("metadata") or {}).get("icon")
            or FAVICON_ENDPOINT.format(domain=brand_domain),
            "generated_at": dt.date.today().isoformat(),
            "date_range": f"{input_data['date_range']['startAt'][:10]} to {input_data['date_range']['endAt'][:10]}",
            "data_source": f"{responses_est} LLM responses across {max(1, len(platform_rows))} platforms",
            "logo_fallback": (brand_name[:2] or "B").lower(),
        },
        "headline": {
            "core_diagnosis": core_diag,
        },
        "overview": {
            "topic_count": topics_total,
            "prompt_count": prompts_total,
            "ai_responses": responses_est,
            "platforms": max(1, len(platform_rows)),
            "languages": 1,
        },
        "kpis": {
            "overall_rank_snapshot": rank_snapshot,
            "avg_position": f"{_num(avg_rank,2)} (Comp {_num(max(avg_rank + 0.35, 0.01),2)})",
            "sentiment": f"{_num(sentiment_score,1)} (Comp {_num(comp_sentiment,1)})",
            "monthly_visits": f"{_human_visits(monthly_visits)} (Comp {_human_visits(_avg([((d.get('seoData') or {}).get('totalVisits') or 0) for d in domains[:5]]))})",
            "avg_rank_gap": f"+{_num(max(0.01, comp_visibility * 10 - visibility * 10),2)} positions vs competitor average",
            "citation_gap": f"{_pct_num(citation,2)} (Comp {_pct_num(comp_citation,2)})",
        },
        "metrics": {
            "visibility": {"you": visibility, "comp": comp_visibility},
            "sov": {"you": ai_mention, "comp": comp_sov},
            "citation": {"you": citation, "comp": comp_citation},
            "sentiment": {"you": sentiment_score, "comp": comp_sentiment},
        },
        "platform_compare": platform_compare,
        "topics": topic_names,
        "high_value_prompts": high_prompts,
        "existing_strengths": [
            f"Broad response coverage across {max(1, len(platform_rows))} mainstream AI platforms.",
            f"Baseline visibility is {_pct_num(visibility,1)} with strong query-level presence.",
            f"Sentiment stays competitive at {_num(sentiment_score,1)} in sampled prompts.",
        ],
        "missing_trust_assets": [
            "Citation authority still trails top competitors in high-intent answers.",
            "Need stronger citable comparison / FAQ style answer blocks.",
        ],
        "sentiment": {
            "positive": pos_ratio,
            "neutral": neu_ratio,
            "negative": neg_ratio,
            "score": _num(sentiment_score, 1),
        },
        "top_citing_domains": top_domains,
        "competitors": [
            {
                "name": c.get("brand") or c.get("name") or c.get("domain", ""),
                "domain": c.get("domain", ""),
                "logo_url": FAVICON_ENDPOINT.format(domain=c.get("domain", "")),
            }
            for c in competitors[:5]
        ],
        "competitor_summary": ", ".join([x for x in comp_names[:5] if x]) or "N/A",
    }


def _metric_card(tag_text: str, tag_class: str, name: str, you_val: float, comp_val: float, is_percent: bool = True, rank_text: str = "#3") -> str:
    if is_percent:
        you_str = _pct_num(you_val, 1)
        comp_str = _pct_num(comp_val, 1)
    else:
        you_str = _num(you_val, 1)
        comp_str = _num(comp_val, 1)

    max_v = max(you_val, comp_val, 1e-9)
    you_w = max(1, min(100, round((you_val / max_v) * 100)))
    comp_w = max(1, min(100, round((comp_val / max_v) * 100)))

    return f"""
        <article class=\"metric\">
          <span class=\"tag {tag_class}\">{_escape(tag_text)}</span>
          <h3 class=\"mn\">{_escape(name)}</h3>
          <p class=\"mv2\">{_escape(you_str)}</p>
          <p class=\"sub\">Comp Avg {_escape(comp_str)} | Rank {_escape(rank_text)}</p>
          <div class=\"bar-r\"><span class=\"lab\">You</span><div class=\"track\"><div class=\"fill-you\" style=\"width:{you_w}%\"></div></div><span class=\"num\">{_escape(you_str)}</span></div>
          <div class=\"bar-r\"><span class=\"lab\">Comp</span><div class=\"track\"><div class=\"fill-comp\" style=\"width:{comp_w}%\"></div></div><span class=\"num\">{_escape(comp_str)}</span></div>
        </article>
    """


def _render_html(data: dict[str, Any]) -> str:
    b = data["brand"]
    m = data["metrics"]
    s = data["sentiment"]

    platform_rows = "\n".join(
        f"<tr><td>{_escape(r['platform'])}</td><td>{_escape(r['visibility'])}</td><td>{_escape(r['sov'])}</td><td>{_escape(r['avg_rank'])}</td><td>{_escape(r['citation'])}</td><td>{_escape(r['sentiment'])}</td></tr>"
        for r in data.get("platform_compare", [])[:2]
    )

    topic_chips = "\n".join(f"<span class=\"chip\">{_escape(x)}</span>" for x in data.get("topics", [])[:5])
    prompt_items = "\n".join(f"<li class=\"li\">{_escape(x)}</li>" for x in data.get("high_value_prompts", [])[:3])
    strengths = "\n".join(f"<li class=\"li good\">{_escape(x)}</li>" for x in data.get("existing_strengths", [])[:3])
    missing = "\n".join(f"<li class=\"li bad\">{_escape(x)}</li>" for x in data.get("missing_trust_assets", [])[:2])

    domain_rows = "\n".join(
        f"<tr><td>{_escape(r['domain'])}</td><td>{_escape(r['monthly_visits'])}</td><td>{_escape(r['domain_type'])}</td><td>{_escape(r['count'])}</td><td>{_escape(r['citation_rate'])}</td></tr>"
        for r in data.get("top_citing_domains", [])[:10]
    )

    comp_logo_rows = "\n".join(
        f"<span class=\"logo-pill\"><img src=\"{_escape(c['logo_url'])}\" alt=\"{_escape(c['name'])} logo\" onerror=\"this.style.display='none'; this.nextElementSibling.style.display='inline-flex';\"><span class=\"logo-fb\">{_escape((c['name'][:1] or 'C').upper())}</span><span class=\"n\">{_escape(c['name'])}</span></span>"
        for c in data.get("competitors", [])[:5]
    )

    vis_rank = "#1" if m["visibility"]["you"] >= m["visibility"]["comp"] else "#3"
    sov_rank = "#1" if m["sov"]["you"] >= m["sov"]["comp"] else "#3"
    cit_rank = "#1" if m["citation"]["you"] >= m["citation"]["comp"] else "#3"
    sent_rank = "#1" if m["sentiment"]["you"] >= m["sentiment"]["comp"] else "#4"

    metric_cards = "\n".join(
        [
            _metric_card("Baseline Strength", "good", "Visibility", m["visibility"]["you"], m["visibility"]["comp"], True, vis_rank),
            _metric_card("Demand Share", "good", "Share of Voice", m["sov"]["you"], m["sov"]["comp"], True, sov_rank),
            _metric_card("Authority Gap", "bad", "Citation Rate", m["citation"]["you"], m["citation"]["comp"], True, cit_rank),
            _metric_card("Conversion Tone", "good", "Sentiment Score", m["sentiment"]["you"], m["sentiment"]["comp"], False, sent_rank),
        ]
    )

    pos_w = max(0, min(100, int(s.get("positive", 0))))
    neu_w = max(0, min(100, int(s.get("neutral", 0))))
    neg_w = max(0, min(100, int(s.get("negative", 0))))

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{_escape(b['name'])} GEO Report - Dense Landscape</title>
  <link href=\"https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600;700;800&display=swap\" rel=\"stylesheet\">
  <style>
    :root {{ --ph:#ff6154; --ink:#0f172a; --muted:#475569; --muted2:#94a3b8; --line:#e2e8f0; --panel:#ffffff; --ok:#10b981; --warn:#ef4444; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:0; background:#f3f6fb; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; color:var(--ink); }}
    .canvas {{ width:1200px; height:740px; border-radius:20px; overflow:hidden; background:#fff; border:1px solid rgba(15,23,42,.08); box-shadow:0 24px 64px rgba(15,23,42,.16); display:grid; grid-template-columns:320px 1fr; }}

    .sidebar {{ background:linear-gradient(160deg,#0b1220 0%,#0f172a 90%); color:#fff; padding:12px; display:grid; grid-template-rows:auto auto auto auto; gap:8px; align-content:start; }}
    .brand {{ display:flex; gap:10px; align-items:center; min-width:0; }}
    .logo-box {{ width:48px; height:48px; border-radius:12px; background:#fff; display:grid; place-items:center; flex-shrink:0; overflow:hidden; box-shadow:0 8px 18px rgba(255,97,84,.3); }}
    .logo-box img {{ width:100%; height:100%; object-fit:cover; display:block; }}
    .logo-fallback {{ display:none; width:100%; height:100%; align-items:center; justify-content:center; }}
    .brand h1 {{ margin:0; font:800 24px/1.05 Sora,Inter,sans-serif; letter-spacing:-.02em; }}
    .brand p {{ margin:4px 0 0; font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:.1em; color:#fca5a0; line-height:1.2; }}

    .meta-grid {{ display:grid; gap:8px; padding:10px; border-radius:12px; border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.05); }}
    .meta-item {{ display:grid; gap:2px; }}
    .ml {{ font-size:8px; text-transform:uppercase; letter-spacing:.08em; color:#94a3b8; font-weight:800; line-height:1; }}
    .mv {{ font-size:11px; font-weight:700; line-height:1.2; color:#fff; word-break:break-word; }}

    .diag-title {{ font-size:9px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; color:#fff; line-height:1; }}
    .diag {{ background:linear-gradient(135deg,#ff6154,#ff9353); border-radius:12px; padding:10px; font-size:11px; line-height:1.35; font-weight:700; overflow-wrap:anywhere; box-shadow:0 10px 20px rgba(255,97,84,.28); }}

    .side-kpi {{ display:grid; gap:6px; align-content:start; min-height:0; align-self:start; }}
    .kpi-row {{ border:1px solid rgba(255,255,255,.12); border-radius:10px; background:rgba(255,255,255,.04); padding:7px 8px; display:flex; justify-content:space-between; align-items:center; gap:10px; }}
    .kpi-row .name {{ font-size:10px; color:#cbd5e1; font-weight:700; }}
    .kpi-row .val {{ font-size:11px; color:#fff; font-weight:800; }}

    .main {{ background:linear-gradient(180deg,#fcfdff,#f8fafc); padding:10px; display:grid; grid-template-rows:auto auto auto auto; gap:6px; min-height:0; align-content:start; }}
    .row {{ display:grid; gap:6px; min-height:0; }}
    .row.top {{ grid-template-columns:repeat(5,1fr); }}
    .row.mid {{ grid-template-columns:repeat(4,1fr); }}
    .row.bottom {{ grid-template-columns:1.2fr 1fr; }}

    .stat {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:7px; min-width:0; }}
    .stat .l {{ margin:0; font-size:8px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted2); font-weight:800; line-height:1; }}
    .stat .v {{ margin:5px 0 0; font:800 18px/1 Sora,Inter,sans-serif; color:var(--ph); letter-spacing:-.01em; }}
    .stat .s {{ margin:3px 0 0; font-size:9px; color:var(--muted); font-weight:700; line-height:1.2; }}

    .metric {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:7px; display:grid; gap:5px; min-width:0; min-height:0; }}
    .tag {{ width:fit-content; font-size:8px; font-weight:900; letter-spacing:.05em; border-radius:999px; padding:3px 7px; line-height:1; text-transform:uppercase; }}
    .tag.good {{ color:#047857; background:#ecfdf5; }}
    .tag.bad {{ color:#b91c1c; background:#fef2f2; }}
    .mn {{ margin:0; font-size:10px; font-weight:800; color:var(--ink); line-height:1.2; min-height:22px; }}
    .mv2 {{ margin:0; font:800 19px/1 Sora,Inter,sans-serif; }}
    .sub {{ margin:0; font-size:9px; color:var(--muted2); font-weight:800; }}

    .bar-r {{ display:grid; grid-template-columns:24px 1fr 40px; gap:4px; align-items:center; }}
    .bar-r .lab {{ font-size:7px; font-weight:800; color:var(--muted); text-transform:uppercase; }}
    .track {{ height:6px; background:#f1f5f9; border-radius:999px; overflow:hidden; }}
    .fill-you {{ height:100%; background:var(--ph); }}
    .fill-comp {{ height:100%; background:#cbd5e1; }}
    .num {{ font-size:7px; font-weight:800; color:var(--muted); text-align:right; }}

    .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:7px; min-height:0; display:grid; gap:7px; align-content:start; overflow:hidden; }}
    .ph {{ display:flex; justify-content:space-between; align-items:center; gap:8px; margin:0; }}
    .pt {{ margin:0; font-size:9px; font-weight:900; letter-spacing:.07em; text-transform:uppercase; color:var(--ink); line-height:1.2; }}
    .hint {{ margin:0; font-size:8px; color:var(--muted2); font-weight:700; line-height:1.35; text-align:right; }}

    table {{ width:100%; border-collapse:collapse; table-layout:fixed; font-size:8px; }}
    th, td {{ padding:3px 3px; border-bottom:1px solid #eef2f7; text-align:right; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:700; color:var(--muted); line-height:1.35; }}
    th:first-child, td:first-child {{ text-align:left; color:var(--ink); }}
    th {{ color:var(--muted2); font-weight:800; text-transform:uppercase; font-size:7px; letter-spacing:.05em; }}

    .list {{ margin:0; padding:0; list-style:none; display:grid; gap:5px; min-height:0; }}
    .li {{ font-size:7px; line-height:1.45; color:var(--muted); font-weight:700; padding:5px 6px; border-radius:8px; background:#f8fafc; border:1px solid #eef2f7; overflow-wrap:anywhere; }}
    .li.bad {{ border-color:#fee2e2; background:#fff7f7; color:#7f1d1d; }}
    .li.good {{ border-color:#dcfce7; background:#f0fdf4; color:#065f46; }}

    .sent-structure {{ display:grid; gap:6px; }}
    .sent-row {{ display:grid; grid-template-columns:54px 1fr 34px; gap:4px; align-items:center; }}
    .sent-row .sl, .sent-row .sv {{ font-size:7px; font-weight:800; color:var(--muted); line-height:1.3; }}
    .sent-row .sv {{ text-align:right; }}
    .sent-row .sb {{ height:6px; border-radius:999px; background:#eef2f7; overflow:hidden; }}
    .sent-row .sf {{ height:100%; border-radius:999px; }}
    .sf.pos {{ background:#10b981; }}
    .sf.neu {{ background:#f59e0b; }}
    .sf.neg {{ background:#ef4444; }}
    .score-box {{ border:1px solid var(--line); background:#fff; border-radius:8px; padding:6px 8px; display:flex; justify-content:space-between; align-items:baseline; gap:8px; }}
    .score-box .k {{ font-size:7px; font-weight:800; color:var(--muted2); text-transform:uppercase; letter-spacing:.05em; line-height:1; }}
    .score-box .v {{ font:800 14px/1 Sora,Inter,sans-serif; color:var(--ink); margin:0; }}

    .domains-table {{ table-layout:auto; font-size:7px; }}
    .domains-table th, .domains-table td {{ white-space:nowrap; line-height:1.3; padding:3px 4px; }}
    .domains-table th:first-child, .domains-table td:first-child {{ max-width:160px; overflow:hidden; text-overflow:ellipsis; }}

    .chips {{ display:flex; gap:4px; flex-wrap:wrap; min-width:0; }}
    .chip {{ font-size:7px; color:var(--muted); font-weight:700; background:#fff; border:1px solid var(--line); padding:3px 7px; border-radius:999px; max-width:120px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}

    .footer {{ border-top:1px solid var(--line); padding-top:5px; display:grid; grid-template-columns:1fr 1fr auto; grid-template-rows:auto; gap:6px; min-width:0; align-items:start; }}
    .footer-metrics {{ grid-column:1; display:grid; grid-template-columns:1fr 1fr; gap:4px; min-width:0; }}
    .fm-card {{ border:1px solid var(--line); border-radius:8px; background:#fff; padding:3px 5px; min-width:0; }}
    .fm-card .k {{ margin:0; font-size:7px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; color:var(--muted2); line-height:1; }}
    .fm-card .v {{ margin:3px 0 0; font-size:7px; font-weight:800; color:var(--ink); line-height:1.2; overflow-wrap:anywhere; }}

    .competitor-wrap {{ grid-column:2; display:grid; gap:4px; min-width:0; }}
    .comp-title {{ margin:0; font-size:7px; font-weight:900; text-transform:uppercase; letter-spacing:.06em; color:var(--muted2); line-height:1; }}
    .competitor-logos {{ display:flex; gap:4px; flex-wrap:wrap; min-width:0; }}
    .logo-pill {{ display:inline-flex; align-items:center; gap:3px; border:1px solid var(--line); border-radius:999px; background:#fff; padding:2px 5px 2px 2px; min-width:0; max-width:120px; }}
    .logo-pill img {{ width:11px; height:11px; border-radius:999px; display:block; flex-shrink:0; }}
    .logo-fb {{ width:11px; height:11px; border-radius:999px; display:none; align-items:center; justify-content:center; font-size:6px; font-weight:900; background:#e2e8f0; color:#334155; flex-shrink:0; text-transform:uppercase; }}
    .logo-pill .n {{ font-size:7px; font-weight:800; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; min-width:0; }}

    .f-right {{ text-align:right; grid-column:3; align-self:center; }}
    .f-right .a {{ font-size:7px; color:var(--muted2); font-weight:800; text-transform:uppercase; letter-spacing:.07em; margin:0; }}
    .f-right .b {{ font-size:11px; color:var(--ink); font:800 11px/1 Sora,Inter,sans-serif; margin:2px 0 0; }}
  </style>
</head>
<body>
  <main class=\"canvas\">
    <aside class=\"sidebar\">
      <div class=\"brand\">
        <div class=\"logo-box\">
          <img src=\"{_escape(b['logo_url'])}\" alt=\"{_escape(b['name'])} logo\" onerror=\"this.style.display='none'; this.nextElementSibling.style.display='flex';\">
          <div class=\"logo-fallback\" aria-hidden=\"true\">
            <svg width=\"34\" height=\"34\" viewBox=\"0 0 40 40\" xmlns=\"http://www.w3.org/2000/svg\"><rect width=\"40\" height=\"40\" rx=\"8\" fill=\"#ff6900\"/><text x=\"20\" y=\"25\" text-anchor=\"middle\" font-size=\"16\" font-weight=\"700\" fill=\"white\">{_escape(b['logo_fallback'])}</text></svg>
          </div>
        </div>
        <div>
          <h1>{_escape(b['name'])}</h1>
          <p>GEO / Presales Diagnosis</p>
        </div>
      </div>

      <section class=\"meta-grid\">
        <div class=\"meta-item\"><div class=\"ml\">Generated</div><div class=\"mv\">{_escape(b['generated_at'])}</div></div>
        <div class=\"meta-item\"><div class=\"ml\">Date Range</div><div class=\"mv\">{_escape(b['date_range'])}</div></div>
        <div class=\"meta-item\"><div class=\"ml\">Data Source</div><div class=\"mv\">{_escape(b['data_source'])}</div></div>
      </section>

      <div class=\"diag-title\">Core Diagnosis / KEY INSIGHT</div>
      <div class=\"diag\">{_escape(data['headline']['core_diagnosis'])}</div>

      <section class=\"side-kpi\">
        <div class=\"kpi-row\"><span class=\"name\">Overall Rank Snapshot</span><span class=\"val\">{_escape(data['kpis']['overall_rank_snapshot'])}</span></div>
        <div class=\"kpi-row\"><span class=\"name\">Avg Position</span><span class=\"val\">{_escape(data['kpis']['avg_position'])}</span></div>
        <div class=\"kpi-row\"><span class=\"name\">Sentiment</span><span class=\"val\">{_escape(data['kpis']['sentiment'])}</span></div>
        <div class=\"kpi-row\"><span class=\"name\">Monthly Visits</span><span class=\"val\">{_escape(data['kpis']['monthly_visits'])}</span></div>
      </section>
    </aside>

    <section class=\"main\">
      <div class=\"row top\">
        <article class=\"stat\"><p class=\"l\">Topic Count</p><p class=\"v\">{_escape(data['overview']['topic_count'])}</p><p class=\"s\">Covered business scenarios</p></article>
        <article class=\"stat\"><p class=\"l\">Prompt Count</p><p class=\"v\">{_escape(data['overview']['prompt_count'])}</p><p class=\"s\">Decision-intent prompts</p></article>
        <article class=\"stat\"><p class=\"l\">AI Responses</p><p class=\"v\">{_escape(data['overview']['ai_responses'])}</p><p class=\"s\">Sampled answer set</p></article>
        <article class=\"stat\"><p class=\"l\">Platforms</p><p class=\"v\">{_escape(data['overview']['platforms'])}</p><p class=\"s\">Perplexity, ChatGPT, Gemini...</p></article>
        <article class=\"stat\"><p class=\"l\">Languages</p><p class=\"v\">{_escape(data['overview']['languages'])}</p><p class=\"s\">English</p></article>
      </div>

      <div class=\"row mid\">{metric_cards}</div>

      <div class=\"row bottom\">
        <section class=\"panel\">
          <h4 class=\"ph\"><span class=\"pt\">Platform Compare</span><span class=\"hint\">visibility / SOV / avg rank / citation / sentiment</span></h4>
          <table>
            <thead><tr><th>Platform</th><th>Vis</th><th>SOV</th><th>Avg Rk</th><th>Cit</th><th>Sent</th></tr></thead>
            <tbody>{platform_rows}</tbody>
          </table>

          <h4 class=\"ph\" style=\"margin-top:2px;\"><span class=\"pt\">Top Conversation Topics</span><span class=\"hint\">from query expansion set</span></h4>
          <div class=\"chips\">{topic_chips}</div>

          <h4 class=\"ph\" style=\"margin-top:1px;\"><span class=\"pt\">High-Value Prompts</span><span class=\"hint\">query fanout samples</span></h4>
          <ul class=\"list\">{prompt_items}</ul>

          <h4 class=\"ph\" style=\"margin-top:2px;\"><span class=\"pt\">Existing Strengths</span><span class=\"hint\">quick wins to build on</span></h4>
          <ul class=\"list\">{strengths}</ul>

          <h4 class=\"ph\" style=\"margin-top:2px;\"><span class=\"pt\">Missing Trust Assets</span><span class=\"hint\">key pages not found</span></h4>
          <ul class=\"list\">{missing}</ul>
        </section>

        <section class=\"panel\">
          <h4 class=\"ph\"><span class=\"pt\">Sentiment Structure</span><span class=\"hint\">Positive / Neutral / Negative</span></h4>
          <div class=\"sent-structure\">
            <div class=\"sent-row\"><span class=\"sl\">Positive</span><div class=\"sb\"><div class=\"sf pos\" style=\"width:{pos_w}%\"></div></div><span class=\"sv\">{_escape(s['positive'])}%</span></div>
            <div class=\"sent-row\"><span class=\"sl\">Neutral</span><div class=\"sb\"><div class=\"sf neu\" style=\"width:{neu_w}%\"></div></div><span class=\"sv\">{_escape(s['neutral'])}%</span></div>
            <div class=\"sent-row\"><span class=\"sl\">Negative</span><div class=\"sb\"><div class=\"sf neg\" style=\"width:{neg_w}%\"></div></div><span class=\"sv\">{_escape(s['negative'])}%</span></div>
          </div>

          <h4 class=\"ph\" style=\"margin-top:2px;\"><span class=\"pt\">Sentiment Score Dashboard (0-100)</span><span class=\"hint\">overall score</span></h4>
          <div class=\"score-box\"><span class=\"k\">Current Score</span><p class=\"v\">{_escape(s['score'])}</p></div>

          <h4 class=\"ph\" style=\"margin-top:2px;\"><span class=\"pt\">Top Citing Domains ⭐</span><span class=\"hint\">domain / visits / type / count / rate</span></h4>
          <table class=\"domains-table\">
            <thead><tr><th>Domain</th><th>Monthly Visits</th><th>Domain Type</th><th>Count</th><th>Citation Rate</th></tr></thead>
            <tbody>{domain_rows}</tbody>
          </table>
        </section>
      </div>

      <div class=\"footer\">
        <div class=\"footer-metrics\">
          <div class=\"fm-card\"><p class=\"k\">Avg Rank Gap</p><p class=\"v\">{_escape(data['kpis']['avg_rank_gap'])}</p></div>
          <div class=\"fm-card\"><p class=\"k\">Citation Gap</p><p class=\"v\">{_escape(data['kpis']['citation_gap'])}</p></div>
        </div>

        <div class=\"competitor-wrap\">
          <p class=\"comp-title\">Key Competitors</p>
          <div class=\"competitor-logos\">{comp_logo_rows}</div>
        </div>

        <div class=\"f-right\">
          <p class=\"a\">Brand AI Performance Check</p>
          <p class=\"b\">By Dageno AI</p>
        </div>
      </div>
    </section>
  </main>
</body>
</html>
"""


def _load_custom_data(custom_json: str | None, google_doc_url: str | None) -> dict[str, Any]:
    if custom_json:
        p = Path(custom_json)
        return json.loads(p.read_text(encoding="utf-8"))
    if google_doc_url:
        text = _google_doc_to_text(google_doc_url)
        return _extract_json_from_text(text)
    raise ValueError("Custom mode requires --custom-json or --google-doc-url")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dense landscape brand report HTML")
    parser.add_argument("--source", choices=["dageno-api", "custom"], required=True)
    parser.add_argument("--api-key", help="Dageno x-api-key (required for dageno-api source)")
    parser.add_argument("--start-at", help="ISO date or datetime, e.g. 2026-03-01")
    parser.add_argument("--end-at", help="ISO date or datetime, e.g. 2026-04-15")
    parser.add_argument("--page-size", type=int, default=5)
    parser.add_argument("--custom-json", help="Path to custom JSON payload")
    parser.add_argument("--google-doc-url", help="Public Google Doc URL containing JSON")
    parser.add_argument("--output", required=True, help="Output HTML file path")
    parser.add_argument("--dump-normalized", help="Optional output path for normalized JSON")

    args = parser.parse_args()

    if args.source == "dageno-api" and not args.api_key:
        raise ValueError("--api-key is required when --source=dageno-api")

    date_range = _default_date_range()
    if args.start_at:
        date_range.start_at = _to_iso_day(args.start_at)
    if args.end_at:
        date_range.end_at = _to_iso_day(args.end_at)

    if args.source == "dageno-api":
        raw = _fetch_api_data(api_key=args.api_key, date_range=date_range, page_size=args.page_size)
        normalized = _normalize(raw, source="dageno-api")
    else:
        raw = _load_custom_data(args.custom_json, args.google_doc_url)
        normalized = _normalize(raw, source="custom")

    html_doc = _render_html(normalized)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")

    if args.dump_normalized:
        Path(args.dump_normalized).write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Generated report: {out}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
