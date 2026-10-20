"""Fetch remote technical-writing leads, drop ones already seen, and draft a
pitch for each. Writes leads.md only when there is something new."""
import json
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SEEN_FILE = Path("data/seen.json")
OUT_FILE = Path("leads.md")

QUERIES = ["technical writer", "documentation", "developer content"]
TITLE_KEYWORDS = [
    "technical writer", "technical writing", "documentation", "docs engineer",
    "content engineer", "api writer", "developer content", "developer docs",
]
PART_TIME_HINTS = ["part-time", "part time", "contract", "freelance"]

PORTFOLIO_URL = os.environ.get("PORTFOLIO_URL") or "https://YOUR-USER.github.io/technical-writing-portfolio/"
YOUR_NAME = os.environ.get("YOUR_NAME") or "Your Name"
SAMPLE_TITLE = os.environ.get("SAMPLE_TITLE") or "How to Configure an IPsec Site-to-Site VPN Tunnel"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "portfolio-lead-bot/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def from_remotive():
    leads = []
    for q in QUERIES:
        try:
            url = "https://remotive.com/api/remote-jobs?search=" + urllib.parse.quote(q)
            data = json.loads(fetch(url))
        except Exception as exc:  # one failing source must not stop the run
            print(f"Remotive '{q}' failed: {exc}")
            continue
        for job in data.get("jobs", []):
            leads.append({
                "id": f"remotive-{job['id']}",
                "title": job.get("title", ""),
                "company": job.get("company_name", ""),
                "url": job.get("url", ""),
                "type": job.get("job_type", ""),
                "source": "Remotive",
            })
    return leads


def from_wwr():
    try:
        root = ET.fromstring(fetch("https://weworkremotely.com/remote-jobs.rss"))
    except Exception as exc:
        print(f"We Work Remotely failed: {exc}")
        return []
    leads = []
    for item in root.iter("item"):
        raw = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        company, _, title = raw.partition(":")
        leads.append({
            "id": f"wwr-{link}",
            "title": title.strip() or raw,
            "company": company.strip() if title else "",
            "url": link,
            "type": "",
            "source": "We Work Remotely",
        })
    return leads


def relevant(lead):
    title = lead["title"].lower()
    return any(k in title for k in TITLE_KEYWORDS)


def pitch(lead):
    company = lead["company"] or "your team"
    return (
        f"Hi {company} team, I saw the {lead['title']} opening and wanted to reach out directly. "
        f"I'm a technical writer with hands-on networking, cloud, and DevOps experience, and I wrote "
        f"\"{SAMPLE_TITLE}\" as a sample of how I document complex infrastructure: {PORTFOLIO_URL} "
        f"Happy to send a short plan for the docs you need most, and I'm available part-time. - {YOUR_NAME}"
    )


def main():
    seen = set(json.loads(SEEN_FILE.read_text())) if SEEN_FILE.exists() else set()

    leads, ids = [], set()
    for lead in from_remotive() + from_wwr():
        if lead["id"] in ids or not relevant(lead):
            continue
        ids.add(lead["id"])
        leads.append(lead)

    new = [l for l in leads if l["id"] not in seen]
    print(f"{len(leads)} relevant, {len(new)} new")

    SEEN_FILE.parent.mkdir(exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen | ids), indent=2))

    if not new:
        OUT_FILE.unlink(missing_ok=True)
        return

    lines = [f"**{len(new)} new lead(s).** Review each one, then paste the pitch into the listing's apply form.\n"]
    for l in new:
        flag = " (part-time/contract)" if any(h in l["type"].lower() for h in PART_TIME_HINTS) else ""
        lines += [
            f"### {l['title']} - {l['company'] or 'Unknown company'}{flag}",
            f"Source: {l['source']} | {l['url']}\n",
            "```text", pitch(l), "```\n",
        ]
    OUT_FILE.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
