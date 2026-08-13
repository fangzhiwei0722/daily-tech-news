#!/usr/bin/env python3
"""
GitHub + 社区 每日技术资讯收集器（AI 优先版）

抓取内容：
- GitHub AI 特别关注（topic:ai, machine-learning, llm, deep-learning 等）
- GitHub 各语言热门项目（按 stars 排序，AI 项目优先展示）
- 近期活跃的 AI 高星项目
- Hacker News AI/技术相关热帖
- Reddit r/programming AI 相关热门帖子

输出：Markdown 文件，AI 内容优先排在最前面。
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
    r = subprocess.run(cmd, capture_output=True, text=text, timeout=30)
    return r.stdout.strip(), r.returncode


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def fetch_url(url: str, headers=None, timeout: int = 15) -> str:
    if headers is None:
        headers = {}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"


def gh_api(path: str) -> Optional[Union[Dict, List]]:
    out, rc = run(["gh", "api", path])
    if rc != 0:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def gh_search(query: str, sort: str = "stars", per_page: int = 20) -> List:
    import urllib.parse
    encoded = urllib.parse.quote(query, safe='')
    path = f"/search/repositories?q={encoded}&sort={sort}&per_page={per_page}"
    data = gh_api(path)
    if isinstance(data, dict):
        return data.get("items", [])
    return []


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_ai_related(repository: Dict) -> bool:
    """判断一个仓库是否与 AI 相关"""
    topics = [t.lower() for t in (repository.get("topics") or [])]
    description = (repository.get("description") or "").lower()
    name = (repository.get("full_name") or "").lower()

    ai_topics = [
        "ai", "machine-learning", "deep-learning", "llm", "chatgpt",
        "gpt", "openai", "anthropic", "claude", "gemini", "llama",
        "diffusion", "transformer", "neural-network", "nlp",
        "computer-vision", "reinforcement-learning", "agent",
        "autogpt", "langchain", "_llama", "embedding", "rag",
        "generative-ai", "text-to-image", "text-to-video",
        "speech-recognition", "speech-synthesis", "audio-ai",
        "ai-chatbot", "chatbot", "conversational-ai",
    ]
    ai_keywords_in_desc = [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "llm", "large language model", "neural", "gpt", "transformer",
        "language model", "diffusion", "reinforcement learning",
        "computer vision", "nlp", "embedding", "agent", "chatbot",
        " anthropic", "openai", "google deepmind", "meta ai",
        "stability ai", "midjourney", "dall-e", "autogpt",
        "langchain", "llamaindex", "rag",
    ]

    for t in topics:
        if t in ai_topics:
            return True
    for kw in ai_keywords_in_desc:
        if kw in description:
            return True
    for kw in ["ai", "llm", "gpt", "agent", "chatbot", " diffusion"]:
        if kw in name:
            return True
    return False


def classify_ai_type(repository: Dict) -> str:
    """对 AI 项目进行分类"""
    topics = [t.lower() for t in (repository.get("topics") or [])]
    description = (repository.get("description") or "").lower()

    if any(t in topics for t in ["llm", "large-language-model", "gpt", "chat", "chatbot", "conversational"]):
        return "大语言模型 / 对话 AI"
    if any(t in topics for t in ["agent", "autogpt", "langchain", "tool-use"]):
        return "AI Agent / 智能体"
    if any(t in topics for t in ["computer-vision", "image", "diffusion", "text-to-image", "cv"]):
        return "计算机视觉 / 生成式视觉"
    if any(t in topics for t in ["nlp", "text", "translation", "summarization"]):
        return "自然语言处理"
    if any(t in topics for t in ["speech", "audio", "voice", "tts", "asr"]):
        return "语音 AI"
    if any(t in topics for t in ["embedding", "vector", "rag", "search", "retrieval"]):
        return "检索增强 / 向量搜索"
    if any(t in topics for t in [" reinforcement-learning", "rl", "decision"]):
        return "强化学习"
    if any(t in topics for t in ["mlops", "pipeline", "training", "inference", "deploy"]):
        return "MLOps / 部署工具"
    if any(kw in description for kw in ["agent", "autonomous", "auto"]):
        return "AI Agent / 自动化"
    return "AI 基础设施 / 通用"


# ---------------------------------------------------------------------------
# GitHub 数据抓取
# ---------------------------------------------------------------------------

def get_ai_spotlight_repos() -> List[Dict]:
    """
    获取 AI 特别关注的仓库 — 各类 AI 主题搜索，按 stars 排序。
    这是每日报告的第一板块。
    """
    ai_queries = [
        ("AI 综合", "topic:ai stars:>500"),
        ("机器学习", "topic:machine-learning stars:>500"),
        ("大语言模型", "topic:llm stars:>100"),
        ("深度学习", "topic:deep-learning stars:>500"),
        ("AI Agent", "topic:agent stars:>100"),
        ("LLM 工具链", "topic:llamaindex OR topic:langchain stars:>100"),
        ("开源 LLM", "topic:llama stars:>500"),
        ("生成式 AI", "topic:generative-ai stars:>100"),
        ("MLOps", "topic:mlops stars:>100"),
        ("嵌入 / 向量", "topic:embedding stars:>100"),
    ]

    results = []
    seen = set()

    for label, query in ai_queries:
        items = gh_search(query, sort="stars", per_page=10)
        for item in items:
            key = item.get("full_name", "")
            if key in seen:
                continue
            seen.add(key)
            results.append({
                **{
                    "full_name": item.get("full_name", ""),
                    "description": clean_text(item.get("description") or ""),
                    "language": item.get("language", ""),
                    "stars": item.get("stargazers_count", 0),
                    "url": item.get("html_url", ""),
                    "topics": [t for t in (item.get("topics") or []) if t],
                    "forks": item.get("forks_count", 0),
                    "created_at": item.get("created_at", ""),
                    "updated_at": item.get("updated_at", ""),
                },
                "_ai_label": label,
                "_ai_type": classify_ai_type(item),
            })

    results.sort(key=lambda x: x["stars"], reverse=True)

    # 按 AI 类型分组，优先展示不同类型的顶尖项目
    by_type: Dict[str, List] = {}
    for r in results:
        ai_type = r.get("_ai_type", "其他")
        by_type.setdefault(ai_type, []).append(r)

    # 每个类型取 top 3，组成最终列表（优先展示覆盖广的类型）
    final = []
    for ai_type in ["大语言模型 / 对话 AI", "AI Agent / 智能体", "MLOps / 部署工具",
                     "计算机视觉 / 生成式视觉", "自然语言处理",
                     "检索增强 / 向量搜索", "语音 AI", "AI 基础设施 / 通用", "其他"]:
        if ai_type in by_type:
            final.extend(by_type[ai_type][:3])
    return final


def get_trending_repos() -> List[Dict]:
    """获取各语言热门项目（AI 项目优先标记）"""
    results = []
    langs = ["python", "typescript", "javascript", "rust", "go", "cpp", "csharp", "java", "swift", "kotlin", "ruby", "php"]

    for lang in langs:
        items = gh_search(f"language:{lang} stars:>100", sort="stars", per_page=5)
        for item in items:
            ai_flag = is_ai_related(item)
            results.append({
                "full_name": item.get("full_name", ""),
                "description": clean_text(item.get("description") or ""),
                "language": item.get("language", ""),
                "stars": item.get("stargazers_count", 0),
                "url": item.get("html_url", ""),
                "topics": [t for t in (item.get("topics") or []) if t],
                "forks": item.get("forks_count", 0),
                "_is_ai": ai_flag,
            })

    seen = set()
    uniq = []
    for r in results:
        if r["full_name"] in seen:
            continue
        seen.add(r["full_name"])
        uniq.append(r)

    # AI 项目优先排在前面
    uniq.sort(key=lambda x: (not x.get("_is_ai", False), -x["stars"]))
    return uniq[:60]


def get_recent_active_repos() -> List[Dict]:
    """近期活跃的高星项目（AI 相关优先）"""
    items = gh_search("stars:>500 updated:>2025-01-01", sort="updated", per_page=30)
    out = []
    for item in items:
        ai_flag = is_ai_related(item)
        out.append({
            "full_name": item.get("full_name", ""),
            "description": clean_text(item.get("description") or ""),
            "language": item.get("language", ""),
            "stars": item.get("stargazers_count", 0),
            "url": item.get("html_url", ""),
            "updated_at": item.get("updated_at", ""),
            "_is_ai": ai_flag,
        })
    out.sort(key=lambda x: (not x.get("_is_ai", False), -x["stars"]))
    return out[:20]


def get_new_releases() -> List[Dict]:
    """近期有重大 Release 的知名项目（重点关注 AI）"""
    items = gh_search("stars:>1000 updated:>2025-01-01", sort="updated", per_page=25)
    out = []
    for item in items:
        ai_flag = is_ai_related(item)
        out.append({
            "full_name": item.get("full_name", ""),
            "description": clean_text(item.get("description") or ""),
            "language": item.get("language", ""),
            "stars": item.get("stargazers_count", 0),
            "url": item.get("html_url", ""),
            "_is_ai": ai_flag,
        })
    out.sort(key=lambda x: (not x.get("_is_ai", False), -x["stars"]))
    return out[:15]


# ---------------------------------------------------------------------------
# Hacker News — 特别关注 AI
# ---------------------------------------------------------------------------

def get_hn_top_stories() -> List[Dict]:
    """HN 顶部故事，AI 相关优先收录"""
    try:
        data = json.loads(fetch_url("https://hacker-news.firebaseio.com/v0/topstories.json"))
        ids = data[:60]  # 扩大范围，优先选 AI 相关的
    except Exception:
        return []

    # 先收集所有项目，标记 AI 相关
    all_items = []
    for sid in ids:
        try:
            item = json.loads(fetch_url(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"))
        except Exception:
            continue
        if not item or "title" not in item:
            continue
        title = clean_text(item.get("title", ""))
        url = item.get("url") or f"https://news.ycombinator.com/item?id={sid}"

        ai_keywords = [
            "ai", "artificial intelligence", "llm", "gpt", "chatgpt", "claude",
            "anthropic", "openai", "gemini", "llama", "language model",
            "machine learning", "deep learning", "neural", "transformer",
            "diffusion", "midjourney", "stable diffusion", "dalle",
            "reinforcement learning", "ml", "imagenet", "imagenet",
            "embedding", "rag", "agent", "autogpt", "langchain",
            "text-to-image", "text-to-video", "generative ai",
            "computer vision", "nlp", "ai agent", "gpt-4", "gpt-5",
            "reasoning", "training", "fine-tune", "inference",
            "huggingface", "pytorch", "tensorflow", "jax",
        ]
        is_ai = any(kw in title.lower() for kw in ai_keywords)

        tech_keywords = [
            "github", "rust", "python", "typescript", "react", "vue", "angular",
            "linux", "kernel", "api", "golang", "database",
            "sql", "postgres", "mysql", "docker", "kubernetes", "aws", "cloud",
            "javascript", "node", "performance", "compiler",
            "programming", "dev", "developer", "algorithm",
            "open source", "tool", "library", "framework",
            "webassembly", "wasm", "swift", "apple", "ios",
            "android", "kotlin", "java", "dotnet", ".net",
            "tutorial", "how to", "guide", "benchmark", "release",
            "css", "html", "security", "cve", "hack",
        ]
        is_tech = any(kw in title.lower() for kw in tech_keywords)

        all_items.append({
            "title": title,
            "url": url,
            "points": item.get("score", 0),
            "comments": item.get("descendants", 0),
            "author": item.get("by", ""),
            "_is_ai": is_ai,
            "_is_tech": is_tech,
        })

    # AI 优先，技术次之
    all_items.sort(key=lambda x: (not x["_is_ai"], not x["_is_tech"], -x["points"]))
    return all_items[:20]


# ---------------------------------------------------------------------------
# Reddit r/programming — 特别关注 AI
# ---------------------------------------------------------------------------

def get_reddit_programming() -> List[Dict]:
    """Reddit r/programming 热门帖子，AI 优先"""
    try:
        headers = {"User-Agent": "DailyTechCollector/1.0 (github-daily-tech; contact: example@example.com)"}
        raw = fetch_url("https://www.reddit.com/r/programming/hot.json?limit=40", headers=headers)
        if raw.startswith("ERROR"):
            return []
        data = json.loads(raw)
        posts = data.get("data", {}).get("children", [])
    except Exception:
        return []

    ai_keywords = [
        "ai", "artificial intelligence", "llm", "gpt", "chatgpt", "claude",
        "anthropic", "openai", "gemini", "llama", "language model",
        "machine learning", "deep learning", "neural", "transformer",
        "diffusion", "midjourney", "stable diffusion", "dalle",
        "reinforcement learning", "ml", "embedding", "rag", "agent",
        "autogpt", "langchain", "text-to-image", "generative ai",
        "computer vision", "nlp", "ai agent", "gpt-4", "gpt-5",
        "deepmind", "huggingface", "pytorch", "tensorflow",
        "google ai", "meta ai", "microsoft ai", "nvidia",
    ]

    results = []
    for child in posts:
        post = child.get("data", {})
        title = clean_text(post.get("title", ""))
        permalink = post.get("permalink", "")
        url = post.get("url") or f"https://www.reddit.com{permalink}"

        is_ai = any(kw in title.lower() for kw in ai_keywords)

        results.append({
            "title": title,
            "url": url,
            "points": post.get("score", 0),
            "comments": post.get("num_comments", 0),
            "author": post.get("author", ""),
            "_is_ai": is_ai,
        })

    results.sort(key=lambda x: (not x["_is_ai"], -x["points"]))
    return results[:15]


# ---------------------------------------------------------------------------
# Markdown 生成
# ---------------------------------------------------------------------------

def section(title: str) -> str:
    return f"\n## {title}\n\n"


def ai_badge(repo: Dict) -> str:
    """AI 属性标签"""
    ai_type = repo.get("_ai_type", "")
    return f"  🤖 {ai_type}" if ai_type else ""


def repo_line(r: Dict, rank: int) -> str:
    stars = r.get("stars", 0)
    lang = r.get("language") or "-"
    desc = r.get("description") or "（无描述）"
    name = r["full_name"]
    url = r["url"]
    topics = ", ".join(r.get("topics", [])[:3]) if r.get("topics") else ""
    topic_str = f"（标签: {topics}）" if topics else ""
    ai_part = ai_badge(r)
    return (
        f"**{rank}. [{name}]({url})** ⭐{stars} · {lang}{ai_part}\n"
        f"> {desc} {topic_str}\n\n"
    )


def discussion_line(item: Dict, rank: int, source: str) -> str:
    title = item["title"]
    url = item["url"]
    pts = item.get("points", item.get("score", 0))
    comments = item.get("comments", 0)
    author = item.get("author", "")
    ai_flag = "🤖 AI" if item.get("_is_ai") else ""
    return (
        f"**{rank}. [{title}]({url})** 赞 {pts} · 评论 {comments} · {author} {ai_flag}\n\n"
    )


def build_report(ai_spotlight, trending, active, releases, hn, reddit) -> str:
    today = today_str()
    lines = []
    lines.append(f"# 📡 每日编程技术资讯 — {today}\n")
    lines.append(f"**生成时间:** {now_iso()}  \n")
    lines.append(f"> 自动收集自 GitHub、Hacker News、Reddit r/programming。\n")
    lines.append(f"> 🤖 **AI 相关内容优先展示**。\n")

    # 1. AI 特别关注（放在最前面）
    if ai_spotlight:
        lines.append(section("🤖 AI 特别关注（重点推荐）"))
        lines.append("*今日值得关注的 AI 项目，按领域分类*\n")

        by_type: Dict[str, List] = {}
        for r in ai_spotlight:
            ai_type = r.get("_ai_type", "其他")
            by_type.setdefault(ai_type, []).append(r)

        for ai_type, repos in by_type.items():
            lines.append(f"### {ai_type}\n\n")
            for i, r in enumerate(repos, 1):
                # 显示是从哪个查询标签找到的
                label = r.get("_ai_label", "")
                label_str = f" _（来自: {label}）_" if label else ""
                lines.append(repo_line(r, i))
                if label:
                    lines.append(f"> _分类标签: {label}_{label_str}\n")
    else:
        lines.append(section("🤖 AI 特别关注"))
        lines.append("*未找到 AI 相关项目*\n")

    # 2. GitHub 热门（按语言分类，AI 项目优先）
    if trending:
        lines.append(section("🔥 GitHub 热门项目（按语言分类，AI 优先）"))
        lines.append("*各语言生态中 star 数较高的代表性项目，AI 项目已优先排列*\n")
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

    # 3. 近期活跃（AI 优先）
    if active:
        lines.append(section("🔄 近期活跃项目（AI 优先）"))
        lines.append("*最近更新较频繁的知名项目*\n")
        for i, r in enumerate(active, 1):
            lines.append(repo_line(r, i))
    else:
        lines.append(section("🔄 近期活跃项目"))
        lines.append("*未获取到数据*\n")

    # 4. Releases
    if releases:
        lines.append(section("📦 值得关注的项目（近期更新，AI 优先）"))
        for i, r in enumerate(releases, 1):
            lines.append(repo_line(r, i))
    else:
        lines.append(section("📦 值得关注的项目"))
        lines.append("*未获取到数据*\n")

    # 5. Hacker News（AI 优先）
    if hn:
        lines.append(section("📰 Hacker News 热门帖子（AI 优先）"))
        for i, item in enumerate(hn, 1):
            lines.append(discussion_line(item, i, "HN"))
    else:
        lines.append(section("📰 Hacker News"))
        lines.append("*未获取到数据*\n")

    # 6. Reddit（AI 优先）
    if reddit:
        lines.append(section("💬 Reddit r/programming 热门帖子（AI 优先）"))
        for i, item in enumerate(reddit, 1):
            lines.append(discussion_line(item, i, "Reddit"))
    else:
        lines.append(section("💬 Reddit r/programming"))
        lines.append("*未获取到数据*\n")

    lines.append(f"\n---\n*每日技术资讯 · 自动生成于 {today}*\n")
    lines.append(f"*AI 相关内容已优先排序。*_ 🤖\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    print(f"[{now_iso()}] 开始收集每日编程技术资讯（AI 优先）...\n")

    print("正在抓取 AI 特别关注项目...")
    ai_spotlight = get_ai_spotlight_repos()
    print(f"  → 找到 {len(ai_spotlight)} 个 AI 相关项目")

    print("正在抓取 GitHub 热门项目（AI 优先排序）...")
    trending = get_trending_repos()
    print(f"  → 找到 {len(trending)} 个热门项目")

    print("正在抓取近期活跃项目...")
    active = get_recent_active_repos()
    print(f"  → 找到 {len(active)} 个活跃项目")

    print("正在抓取值得关注的项目...")
    releases = get_new_releases()
    print(f"  → 找到 {len(releases)} 个项目")

    print("正在抓取 Hacker News（AI 优先）...")
    hn = get_hn_top_stories()
    print(f"  → 找到 {len(hn)} 条帖子")

    print("正在抓取 Reddit r/programming（AI 优先）...")
    reddit = get_reddit_programming()
    print(f"  → 找到 {len(reddit)} 条帖子")

    report = build_report(ai_spotlight, trending, active, releases, hn, reddit)

    out_path = f"github_daily_tech_{today_str()}.md"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 报告已保存至: {out_path}")

    # 统计 AI 比例
    total_items = len(ai_spotlight) + len(trending) + len(active) + len(releases) + len(hn) + len(reddit)
    ai_items = sum(1 for r in ai_spotlight if True) + sum(1 for r in trending if r.get("_is_ai")) + \
                sum(1 for r in active if r.get("_is_ai")) + sum(1 for r in releases if r.get("_is_ai")) + \
                sum(1 for h in hn if h.get("_is_ai")) + sum(1 for r in reddit if r.get("_is_ai"))
    print(f"\n📊 AI 相关内容占比: {ai_items}/{total_items} ({100*ai_items/max(total_items,1):.0f}%)")

    print("\n=== 摘要（前 2500 字符）===\n")
    print(report[:2500] + ("..." if len(report) > 2500 else ""))


if __name__ == "__main__":
    main()
