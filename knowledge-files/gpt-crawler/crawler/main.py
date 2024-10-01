import asyncio
import json
import fnmatch
from crawler_config import Config
import sys
import os
import requests

from bs4 import BeautifulSoup

KH2RANDO_WEBSITE_URL_START = "https://tommadness.github.io"
KH2RANDO_WEBSITE_KNOWLEDGE_FILENAME = "kh2fmrando-website.json"

async def get_page_html(page, selector):
    await page.wait_for_selector(selector)
    element = await page.query_selector(selector)
    return await element.inner_text() if element else ""


async def crawl(config):
    visited_pages = []
    results = []
    queue = [config.url]

    session = requests.Session()

    if config.cookie:
        session.cookies.set(config.cookie['name'], config.cookie['value'], domain=config.url)

    try:
        while queue and len(results) < config.max_pages_to_crawl:
            try:
                url = queue.pop(0)
                if not url.startswith("http"):
                    url = KH2RANDO_WEBSITE_URL_START + url
                if url in visited_pages:
                    continue
                print(f"Crawler: Crawling {url}")
                response = session.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                html = soup.select_one(config.selector).get_text() if soup.select_one(config.selector) else ""
                results.append({'url': url, 'html': html})
                with open(config.output_file_name, 'w') as f:
                    json.dump(results, f, indent=2)

                # Extract and enqueue links
                links = soup.find_all("a")
                for link in links:
                    href = link.get("href")
                    if href and fnmatch.fnmatch(href, config.match):
                        queue.append(href)

            except:
                pass
            visited_pages.append(url)
    finally:
        session.close()

    return results


async def main(config):

    output_dir = os.path.dirname(config.output_file_name)
    os.makedirs(output_dir, exist_ok=True)
    
    results = await crawl(config)
    with open(config.output_file_name, 'w') as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    config = Config(
        url=KH2RANDO_WEBSITE_URL_START + "/KH2Randomizer",
        match=f"/KH2Randomizer/**",
        selector="#content",
        max_pages_to_crawl=1000,
        output_file_name=os.path.abspath(os.path.join(__file__, "..", "..", "..", "dynamic-files", "kh2rando-website", KH2RANDO_WEBSITE_KNOWLEDGE_FILENAME))
    )
    asyncio.run(main(config))

