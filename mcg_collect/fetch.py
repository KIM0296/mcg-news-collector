"""웹 페이지 가져오기.

- 일반 사이트(WNN 등): requests
- KAIF: 처음 응답에 본문이 비어 오므로, 비어 있으면 실제 브라우저(Playwright)로 다시 연다.
- 시험용: fixtures 폴더를 주면 인터넷 대신 저장된 HTML을 읽는다.
"""
import hashlib
import os
import time

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 MCG-weekly-collector")


class Fetcher:
    def __init__(self, fixtures_dir=None, delay=1.0, cache_dir=None):
        self.fixtures_dir = fixtures_dir
        self.delay = delay          # 사이트에 부담을 주지 않도록 요청 간 간격(초)
        self.cache_dir = cache_dir
        self._browser = None
        self._pw = None
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept-Language": "ko,en;q=0.8"})

    # ---- 시험용 ----
    def _fixture(self, url):
        if not self.fixtures_dir:
            return None
        index = os.path.join(self.fixtures_dir, "index.txt")
        if os.path.exists(index):
            for line in open(index, encoding="utf-8"):
                if "\t" in line:
                    u, fn = line.rstrip("\n").split("\t", 1)
                    if u == url:
                        return open(os.path.join(self.fixtures_dir, fn), encoding="utf-8").read()
        return ""   # 시험 모드에서 없는 페이지는 빈 문자열

    def _cache_path(self, url):
        if not self.cache_dir:
            return None
        os.makedirs(self.cache_dir, exist_ok=True)
        return os.path.join(self.cache_dir, hashlib.md5(url.encode()).hexdigest() + ".html")

    # ---- 일반 ----
    def get(self, url, timeout=30):
        if self.fixtures_dir is not None:
            return self._fixture(url)
        cp = self._cache_path(url)
        if cp and os.path.exists(cp):
            return open(cp, encoding="utf-8").read()
        time.sleep(self.delay)
        r = self.session.get(url, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.encoding or "utf-8"
        text = r.text
        if cp:
            open(cp, "w", encoding="utf-8").write(text)
        return text

    # ---- 브라우저가 필요한 페이지 ----
    def get_rendered(self, url, wait_selector, timeout=40):
        """먼저 일반 요청을 시도하고, wait_selector가 없으면 브라우저로 연다."""
        if self.fixtures_dir is not None:
            return self._fixture(url)
        cp = self._cache_path(url)
        if cp and os.path.exists(cp):
            return open(cp, encoding="utf-8").read()
        try:
            html = self.get(url, timeout=timeout)
            marker = wait_selector.lstrip("#.").split()[0]
            if marker in html and len(html) > 5000:
                return html
        except Exception:
            pass
        html = self._browser_get(url, wait_selector, timeout)
        if cp:
            open(cp, "w", encoding="utf-8").write(html)
        return html

    def _browser_get(self, url, wait_selector, timeout):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError("KAIF 수집에는 Playwright가 필요합니다: pip install playwright && "
                               "python -m playwright install chromium") from e
        if self._browser is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=True)
        time.sleep(self.delay)
        page = self._browser.new_page(user_agent=UA, locale="ko-KR")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_selector(wait_selector, timeout=timeout * 1000)
            return page.content()
        finally:
            page.close()

    def close(self):
        if self._browser:
            self._browser.close()
            self._pw.stop()
            self._browser = None
