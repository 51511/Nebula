"""
Blogroll Crawler (async 版)
============================
用 asyncio + aiohttp 真正並發爬取，等網路時不浪費時間。

用法：
    pip install aiohttp beautifulsoup4
    python blogroll_crawler.py
    python blogroll_crawler.py --seed https://example.com/blogroll --max-depth 3
"""

import argparse
import asyncio
import json
import logging
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

# ── 設定 ──────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BLOGROLL_PATHS = [
    "/blogroll",
    "/blogroll/",
    "/blog_roll",
    "/blog_roll/",
    "/links",
    "/links/",
    "/friends",
    "/friends/",
    "/blogroll.opml",
    "/links.opml",
]

HEADERS = {
    "User-Agent": "BlogrollCrawler/2.0 (personal research)",
    "Accept": "text/html,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=8)
CONCURRENCY = 5      # 同時最多幾個請求（Semaphore 控制）
REQUEST_DELAY = 0.3  # 每個請求前的小延遲（禮貌用）

# ── 過濾清單 ──────────────────────────────────────────────────────────────────
# 這些平台/服務網域不屬於個人部落格，直接排除

# 白名單：這些是個人站托管平台，不管域名比對結果如何都放行
ALLOWED_HOSTING_SUFFIXES = {
    "github.io",       # GitHub Pages
    "gitlab.io",       # GitLab Pages
    "netlify.app",     # Netlify
    "vercel.app",      # Vercel
    "pages.dev",       # Cloudflare Pages
    "render.com",      # Render
    "fly.dev",         # Fly.io
    "surge.sh",        # Surge
    "neocities.org",   # Neocities（個人懷舊風格站）
    "bearblog.dev",    # Bear Blog
    "mataroa.blog",    # Mataroa
    "micro.blog",      # Micro.blog
}

BLOCKED_DOMAINS = {
    # 影音 / 媒體
    "youtube.com", "youtu.be", "vimeo.com", "twitch.tv", "bilibili.com",
    "dailymotion.com", "tiktok.com", "niconico.com", "nicovideo.jp",
    # 程式碼托管（注意：github.io 在白名單，不受此影響）
    "github.com", "gitlab.com", "bitbucket.org", "codeberg.org",
    "sourceforge.net", "gist.github.com",
    # 社群媒體
    "twitter.com", "x.com", "facebook.com", "instagram.com",
    "threads.net", "mastodon.social", "bsky.app", "bluesky.social",
    "linkedin.com", "pinterest.com", "tumblr.com", "reddit.com",
    "weibo.com", "plurk.com", "ptt.cc", "dcard.tw",
    # 新聞 / 媒體機構
    "nytimes.com", "bbc.com", "bbc.co.uk", "cnn.com", "theguardian.com",
    "reuters.com", "apnews.com", "wsj.com", "washingtonpost.com",
    "techcrunch.com", "theverge.com", "wired.com", "arstechnica.com",
    "engadget.com", "zdnet.com", "cnet.com",
    # 電商 / 購物
    "amazon.com", "amazon.co.jp", "ebay.com", "etsy.com", "shopify.com",
    "aliexpress.com", "taobao.com", "jd.com", "rakuten.co.jp",
    # 搜尋引擎
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com", "baidu.com",
    # 雲端 / 儲存 / 工具
    "dropbox.com", "drive.google.com", "onedrive.live.com", "icloud.com",
    "notion.so", "airtable.com", "trello.com", "asana.com",
    # 部落格平台：wordpress.com / blogger.com / blogspot.com 保留（真實個人部落格）
    # 以下只擋純工具型建站平台
    "medium.com", "ghost.io", "weebly.com", "wix.com", "squarespace.com",
    "livejournal.com", "typepad.com",
    # 技術文件 / 知識庫
    "wikipedia.org", "wikimedia.org", "stackoverflow.com", "stackexchange.com",
    "docs.google.com", "readthedocs.io", "gitbook.io",
    # 圖片 / 設計
    "flickr.com", "unsplash.com", "pexels.com", "behance.net", "dribbble.com",
    "deviantart.com", "artstation.com",
    # 音樂串流平台
    "spotify.com", "soundcloud.com", "bandcamp.com", "last.fm",
    "deezer.com", "tidal.com", "pandora.com", "iheart.com",
    "kkbox.com", "joox.com", "streetvoice.com", "audiomack.com",
    "music.apple.com", "music.youtube.com", "music.amazon.com",
    "napster.com", "qobuz.com", "yandex.music", "vk.com",
    "netease.com", "music.163.com", "qq.com", "kugou.com", "kuwo.cn",
    # Podcast 平台
    "anchor.fm", "buzzsprout.com", "podcasts.apple.com",
    "podbean.com", "transistor.fm", "simplecast.com", "spreaker.com",
    "podomatic.com", "libsyn.com", "acast.com", "podcastaddict.com",
    # 其他大型平台
    "paypal.com", "patreon.com", "ko-fi.com", "buymeacoffee.com",
    "t.me", "telegram.org", "discord.com", "discord.gg",
    "slack.com", "zoom.us", "meet.google.com",
    "archive.org", "web.archive.org",
}

# 也封鎖這些關鍵字出現在域名中的情況（例如 cdn.xxx.com、api.xxx.com）
BLOCKED_DOMAIN_KEYWORDS = {
    "cdn.", "api.", "static.", "assets.", "img.", "images.",
    "mail.", "smtp.", "ftp.", "ns1.", "ns2.",
}


def is_blog_domain(domain: str) -> bool:
    """判斷域名是否可能是個人/獨立部落格。回傳 False 代表應排除。"""
    bare = domain.removeprefix("www.")

    # ── 第一步：白名單優先，托管平台直接放行 ──
    # 例如 username.github.io、mysite.netlify.app
    for suffix in ALLOWED_HOSTING_SUFFIXES:
        if bare == suffix or bare.endswith("." + suffix):
            return True

    # ── 第二步：封鎖清單，逐層比對 ──
    # 例如 news.bbc.co.uk → 能比到 bbc.co.uk
    parts = bare.split(".")
    for i in range(len(parts) - 1):
        candidate = ".".join(parts[i:])
        if candidate in BLOCKED_DOMAINS:
            return False

    # ── 第三步：子域名前綴比對 ──
    for kw in BLOCKED_DOMAIN_KEYWORDS:
        if bare.startswith(kw):
            return False

    return True


# ── 工具函數 ──────────────────────────────────────────────────────────────────

def get_domain(url: str) -> str:
    parsed = urlparse(url)
    domain = parsed.netloc
    return domain.removeprefix("www.")


def parse_external_links(html: str, base_url: str, visited_domains: set) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_domain = get_domain(base_url)
    found = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue

        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue

        domain = get_domain(abs_url)
        if not domain or domain == base_domain:
            continue
        if domain in visited_domains or domain in seen:
            continue

        # ── 新增：過濾非部落格網域 ──
        if not is_blog_domain(domain):
            log.debug(f"  ⊘ 過濾非部落格域名: {domain}")
            continue

        seen.add(domain)
        found.append(f"{parsed.scheme}://{parsed.netloc}")

    return found


# ── 非同步核心 ────────────────────────────────────────────────────────────────

async def fetch(session: aiohttp.ClientSession, url: str, sem: asyncio.Semaphore) -> tuple[int, str]:
    async with sem:
        await asyncio.sleep(REQUEST_DELAY)
        try:
            async with session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True) as resp:
                if resp.status == 200:
                    text = await resp.text(errors="replace")
                    return resp.status, text
                return resp.status, ""
        except Exception:
            return 0, ""


async def find_blogroll(session: aiohttp.ClientSession, root_url: str, sem: asyncio.Semaphore) -> tuple[str | None, str | None]:
    """同時試所有路徑，回傳第一個成功的"""
    urls_to_try = [root_url.rstrip("/") + path for path in BLOGROLL_PATHS]

    tasks = [fetch(session, url, sem) for url in urls_to_try]
    results = await asyncio.gather(*tasks)

    for url, (status, html) in zip(urls_to_try, results):
        if status != 200 or len(html) < 200:
            continue
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", href=True)
        if len(links) < 3:
            continue
        log.info(f"  ✓ 找到 Blogroll: {url}  ({len(links)} 個連結)")
        return url, html

    return None, None


async def process_node(
    session, root_url, depth, max_depth, visited_domains, sem
) -> tuple[str, str | None, list[str]]:
    domain = get_domain(root_url)

    if depth >= max_depth:
        log.info(f"[depth={depth}] {domain} → 達到最大深度")
        return domain, None, []

    log.info(f"[depth={depth}] 探索: {domain}")
    blogroll_url, html = await find_blogroll(session, root_url, sem)

    if blogroll_url is None:
        log.info(f"  ✗ 沒有 Blogroll，葉節點")
        return domain, None, []

    new_links = parse_external_links(html, blogroll_url, visited_domains)
    log.info(f"  發現 {len(new_links)} 個新連結")
    return domain, blogroll_url, new_links


# ── 主爬蟲 ────────────────────────────────────────────────────────────────────

async def crawl(seed_url: str, max_depth: int = 3, max_nodes: int = 300) -> dict:
    graph = {}
    visited_domains = set()
    sem = asyncio.Semaphore(CONCURRENCY)

    connector = aiohttp.TCPConnector(
            limit=CONCURRENCY,
            limit_per_host=2,
            ssl=False,
            ttl_dns_cache=300,
        )
    async with aiohttp.ClientSession(connector=connector) as session:

        log.info(f"=== 起點: {seed_url} ===")
        status, html = await fetch(session, seed_url, sem)
        if status != 200:
            log.error(f"無法抓取起始頁面 (status={status})")
            return graph

        seed_domain = get_domain(seed_url)
        visited_domains.add(seed_domain)
        initial_links = parse_external_links(html, seed_url, visited_domains)
        log.info(f"起始頁面解析到 {len(initial_links)} 個外部連結（已過濾非部落格）")

        graph[seed_domain] = {
            "blogroll_url": seed_url,
            "links_to": [get_domain(l) for l in initial_links],
        }

        # asyncio.Queue 做 BFS
        queue: asyncio.Queue = asyncio.Queue()
        for link in initial_links:
            await queue.put((link, 1))

        pending: set[asyncio.Task] = set()

        async def worker():
            while True:
                try:
                    root_url, depth = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                domain = get_domain(root_url)
                if domain in visited_domains:
                    queue.task_done()
                    continue
                visited_domains.add(domain)

                if len(visited_domains) > max_nodes:
                    queue.task_done()
                    break

                domain, blogroll_url, new_links = await process_node(
                    session, root_url, depth, max_depth, visited_domains, sem
                )

                graph[domain] = {
                    "blogroll_url": blogroll_url,
                    "links_to": [get_domain(l) for l in new_links],
                }

                for link in new_links:
                    await queue.put((link, depth + 1))

                queue.task_done()

        while not queue.empty() and len(visited_domains) < max_nodes:
            while len(pending) < CONCURRENCY and not queue.empty():
                task = asyncio.create_task(worker())
                pending.add(task)
                task.add_done_callback(pending.discard)

            if pending:
                await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

    log.info(f"\n=== 完成 ===")
    log.info(f"訪問節點數: {len(visited_domains)}")
    log.info(f"有 Blogroll 的節點數: {sum(1 for v in graph.values() if v['blogroll_url'])}")
    return graph


# ── 輸出 ──────────────────────────────────────────────────────────────────────

def print_summary(graph: dict):
    print("\n" + "="*60)
    print("爬取結果摘要")
    print("="*60)

    has_blogroll = {k: v for k, v in graph.items() if v["blogroll_url"]}
    leaf_nodes   = {k: v for k, v in graph.items() if not v["blogroll_url"]}

    print(f"\n有 Blogroll 的站 ({len(has_blogroll)} 個):")
    for domain, info in sorted(has_blogroll.items(), key=lambda x: -len(x[1]["links_to"])):
        print(f"  {domain:40s}  →  {len(info['links_to'])} 個連結")

    print(f"\n葉節點（無 Blogroll）({len(leaf_nodes)} 個):")
    for domain in sorted(leaf_nodes.keys()):
        print(f"  {domain}")

    in_degree: dict[str, int] = {}
    for info in graph.values():
        for d in info["links_to"]:
            in_degree[d] = in_degree.get(d, 0) + 1

    print(f"\n被連最多次的站（PageRank 雛形）:")
    for domain, count in sorted(in_degree.items(), key=lambda x: -x[1])[:10]:
        print(f"  {domain:40s}  ←  被連 {count} 次")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Blogroll 爬蟲 (async 版)")
    parser.add_argument("--seed", default="https://blog.giveanornot.com/blogroll/")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=300)
    parser.add_argument("--output", default="blogroll_graph.json")
    args = parser.parse_args()

    graph = asyncio.run(crawl(
        seed_url=args.seed,
        max_depth=args.max_depth,
        max_nodes=args.max_nodes,
    ))

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    log.info(f"圖資料已存至 {args.output}")

    print_summary(graph)
