#!/usr/bin/env python3
"""
GitHub + 社区 每日技术资讯收集器（稳健版）

抓取内容：
- GitHub 热门仓库（按语言分组，按 stars 排序）
- 近期更新活跃的高星项目
- Hacker News 编程相关热帖
- Reddit r/programming 热门帖子

输出：Markdown 文件，可直接推送到 GitHub 或发送给用户。

注意：GitHub API 无"当日 trending"接口，这里用按语言搜索 + stars 排序
      近似模拟 trending。Hacker News 和 Reddit 提供真实社区讨论。
"""

import subprocess
import json
import re
import html
from datetime import datetime, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError
from typing import Union, Dict, List, Optional

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def run(cmd: list, text: bool = True):
    """运行命令，返回 (stdout, returncode)"""
    r = subprocess.run(cmd, capture_output=True, text=text, timeout=30)
    return r.stdout.strip(), r.returncode


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_url(url: str, headers=None, timeout: int = 15) -> str:
    """简单 GET，返回字符串，失败返回 ERROR 字符串"""
    if headers is None:
        headers = {}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"


def gh_api(path: str) -> Optional[Union[Dict, List]]:
    """通过 gh CLI 调用 GitHub API，返回 JSON"""
    out, rc = run(["gh", "api", path])
    if rc != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def gh_search(query: str, sort: str = "stars", per_page: int = 20) -> List:
    """GitHub 搜索仓库"""
    # 安全编码 query
    import urllib.parse
    encoded = urllib.parse.quote(query, safe='')
    path = f"/search/repositories?q={encoded}&sort={sort}&per_page={per_page}"
    data = gh_api(path)
    if isinstance(data, dict):
        return data.get("items", [])
    return []


def clean_text(s: str) -> str:
    """基本文本清洗"""
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", "", s)  # 去除 HTML 标签
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# GitHub 数据抓取
# ---------------------------------------------------------------------------

def get_trending_repos() -> List[Dict]:
    """
    获取热门仓库（按语言分类，按 stars 排序）。
    GitHub 无官方 trending API，这里用搜索 + stars 排序近似。
    """
    results = []
    langs = ["python", "javascript", "rust", "go", "typescript", "cpp", "csharp", "java", "swift", "kotlin", "ruby", "php"]
    for lang in langs:
        # 搜索：该语言，至少 100 star，按 stars 排序取前 5
        items = gh_search(f"language:{lang} stars:>100", sort="stars", per_page=5)
        for item in items:
            results.append({
                "full_name": item.get("full_name", ""),
                "description": clean_text(item.get("description") or ""),
                "language": item.get("language", ""),
                "stars": item.get("stargazers_count", 0),
                "url": item.get("html_url", ""),
                "topics": [t for t in (item.get("topics") or []) if t],
                "forks": item.get("forks_count", 0),
            })
    # 去重
    seen = set()
    uniq = []
    for r in results:
        if r["full_name"] in seen:
            continue
        seen.add(r["full_name"])
        uniq.append(r)
    uniq.sort(key=lambda x: x["stars"], reverse=True)
    return uniq[:60]


def get_recent_active_repos() -> List[Dict]:
    """近期更新活跃的高星项目（按更新时间排序）"""
    items = gh_search("stars:>500 updated:>2025-01-01", sort="updated", per_page=30)
    out = []
    for item in items:
        out.append({
            "full_name": item.get("full_name", ""),
            "description": clean_text(item.get("description") or ""),
            "language": item.get("language", ""),
            "stars": item.get("stargazers_count", 0),
            "url": item.get("html_url", ""),
            "updated_at": item.get("updated_at", ""),
        })
    out.sort(key=lambda x: x["stars"], reverse=True)
    return out[:25]


def get_new_releases() -> List[Dict]:
    """近期有重大 Release 的知名项目（按 stars 排序）"""
    items = gh_search("stars:>1000 updated:>2025-01-01", sort="updated", per_page=25)
    out = []
    for item in items:
        out.append({
            "full_name": item.get("full_name", ""),
            "description": clean_text(item.get("description") or ""),
            "language": item.get("language", ""),
            "stars": item.get("stargazers_count", 0),
            "url": item.get("html_url", ""),
        })
    out.sort(key=lambda x: x["stars"], reverse=True)
    return out[:15]


# ---------------------------------------------------------------------------
# Hacker News
# ---------------------------------------------------------------------------

def get_hn_top_stories() -> List[Dict]:
    """HN 顶部故事，过滤出编程相关"""
    try:
        data = json.loads(fetch_url("https://hacker-news.firebaseio.com/v0/topstories.json"))
        ids = data[:50]
    except Exception:
        return []

    results = []
    for sid in ids:
        try:
            item = json.loads(fetch_url(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"))
        except Exception:
            continue
        if not item or "title" not in item:
            continue
        title = clean_text(item.get("title", ""))
        url = item.get("url") or f"https://news.ycombinator.com/item?id={sid}"

        tech_keywords = [
            "github", "rust", "python", "typescript", "react", "vue", "angular",
            "linux", "kernel", "api", "golang", "database",
            "sql", "postgres", "mysql", "docker", "kubernetes", "aws", "cloud",
            "openai", "llm", "ai", "machine learning", "security", "cve",
            "javascript", "node", "performance", "compiler",
            "programming", "dev", "developer", "algorithm",
            "open source", "tool", "library", "framework",
            "webassembly", "wasm", "swift", "apple", "ios",
            "android", "kotlin", "java", "dotnet", ".net",
            "tutorial", "how to", "guide", "benchmark", "release",
            "rust", "go ", "typescript", "css", "html",
        ]
        if any(kw in title.lower() for kw in tech_keywords):
            results.append({
                "title": title,
                "url": url,
                "points": item.get("score", 0),
                "comments": item.get("descendants", 0),
                "author": item.get("by", ""),
            })
    return results[:20]


# ---------------------------------------------------------------------------
# Reddit r/programming
# ---------------------------------------------------------------------------

def get_reddit_programming() -> List[Dict]:
    """Reddit r/programming 热门帖子"""
    try:
        headers = {"User-Agent": "DailyTechCollector/1.0 (github-daily-tech; contact: example@example.com)"}
        raw = fetch_url("https://www.reddit.com/r/programming/hot.json?limit=25", headers=headers)
        if raw.startswith("ERROR"):
            return []
        data = json.loads(raw)
        posts = data.get("data", {}).get("children", [])
    except Exception:
        return []

    results = []
    for child in posts:
        post = child.get("data", {})
        title = clean_text(post.get("title", ""))
        permalink = post.get("permalink", "")
        url = post.get("url") or f"https://www.reddit.com{permalink}"
        results.append({
            "title": title,
            "url": url,
            "points": post.get("score", 0),
            "comments": post.get("num_comments", 0),
            "author": post.get("author", ""),
        })
    return results[:15]


# ---------------------------------------------------------------------------
# Markdown 生成
# ---------------------------------------------------------------------------

def section(title: str) -> str:
    return f"\n## {title}\n\n"


def repo_line(r: Dict, rank: int) -> str:
    stars = r.get("stars", 0)
    lang = r.get("language") or "-"
    desc = r.get("description") or "（无描述）"
    name = r["full_name"]
    url = r["url"]
    topics = ", ".join(r.get("topics", [])[:3]) if r.get("topics") else ""
    topic_str = f"（标签: {topics}）" if topics else ""
    return (
        f"**{rank}. [{name}]({url})** ⭐{stars} · {lang}\n"
        f"> {desc} {topic_str}\n\n"
    )


def discussion_line(item: Dict, rank: int, source: str) -> str:
    title = item["title"]
    url = item["url"]
    pts = item.get("points", item.get("score", 0))
    comments = item.get("comments", 0)
    author = item.get("author", "")
    return (
        f"**{rank}. [{title}]({url})** 赞 {pts} · 评论 {comments} · {author}\n\n"
    )


def build_report(trending, active, releases, hn, reddit) -> str:
    today = today_str()
    lines = []
    lines.append(f"# 📡 每日编程技术资讯 — {today}\n")
    lines.append(f"**生成时间:** {now_iso()}  \n")
    lines.append(f"> 自动收集自 GitHub、Hacker News、Reddit r/programming。\n")

    # 1. GitHub 热门
    if trending:
        lines.append(section("🔥 GitHub 热门项目（按语言分类）"))
        lines.append("*各语言生态中 star 数较高的代表性项目*\n")
        cur_lang = None
        rank = 0
        for r in trending:
            lang = r.get("language") or "-"
            if lang != cur_lang:
                cur_lang = lang
                lines.append(f"### {lang}\n\n")
                rank = 0
            rank += 1
            lines.append(repo_line(r, rank))
    else:
        lines.append(section("🔥 GitHub 热门项目"))
        lines.append("*未获取到数据*\n")

    # 2. 近期活跃
    if active:
        lines.append(section("🔄 近期活跃的高星项目"))
        lines.append("*最近更新较频繁的知名项目*\n")
        for i, r in enumerate(active, 1):
            lines.append(repo_line(r, i))
    else:
        lines.append(section("🔄 近期活跃项目"))
        lines.append("*未获取到数据*\n")

    # 3. Releases
    if releases:
        lines.append(section("📦 值得关注的项目（近期更新）"))
        for i, r in enumerate(releases, 1):
            lines.append(repo_line(r, i))
    else:
        lines.append(section("📦 值得关注的项目"))
        lines.append("*未获取到数据*\n")

    # 4. Hacker News
    if hn:
        lines.append(section("📰 Hacker News 编程相关热帖"))
        for i, item in enumerate(hn, 1):
            lines.append(discussion_line(item, i, "HN"))
    else:
        lines.append(section("📰 Hacker News"))
        lines.append("*未获取到数据*\n")

    # 5. Reddit
    if reddit:
        lines.append(section("💬 Reddit r/programming 热门帖子"))
        for i, item in enumerate(reddit, 1):
            lines.append(discussion_line(item, i, "Reddit"))
    else:
        lines.append(section("💬 Reddit r/programming"))
        lines.append("*未获取到数据*\n")

    lines.append(f"\n---\n*每日技术资讯 · 自动生成于 {today}*\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    print(f"[{now_iso()}] 开始收集每日编程技术资讯...\n")

    print("正在抓取 GitHub 热门项目...")
    trending = get_trending_repos()
    print(f"  → 找到 {len(trending)} 个热门项目")

    print("正在抓取近期活跃项目...")
    active = get_recent_active_repos()
    print(f"  → 找到 {len(active)} 个活跃项目")

    print("正在抓取值得关注的项目...")
    releases = get_new_releases()
    print(f"  → 找到 {len(releases)} 个项目")

    print("正在抓取 Hacker News...")
    hn = get_hn_top_stories()
    print(f"  → 找到 {len(hn)} 条编程相关帖子")

    print("正在抓取 Reddit r/programming...")
    reddit = get_reddit_programming()
    print(f"  → 找到 {len(reddit)} 条热门帖子")

    report = build_report(trending, active, releases, hn, reddit)

    out_path = f"github_daily_tech_{today_str()}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 报告已保存至: {out_path}")

    print("\n=== 摘要（前 2000 字符）===\n")
    print(report[:2000] + ("..." if len(report) > 2000 else ""))


if __name__ == "__main__":
    main()
