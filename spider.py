#-*- coding: utf-8 -*-

import gevent
from gevent import (monkey,
                    queue,
                    event,
                    pool)

import sys
import logging
import requests
from threading import Timer
from utils import HtmlAnalyzer, UrlFilter


__all__ = ['Strategy', 'UrlObj', 'Spider', 'HtmlAnalyzer', 'UrlFilter']


class Strategy(object):

    default_cookies = {}

    default_headers = {
        'User-Agent': 'SinaSec Webscan Spider',
        'Accept': 'Accept:text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',  # noqa
        'Cache-Control': 'max-age=0',
        'Accept-Charset': 'GBK,utf-8;q=0.7,*;q=0.3',
    }

    def __init__(self, max_depth=5, max_count=5000, concurrency=5, timeout=10,
                 time=6 * 3600, headers=None, cookies=None, ssl_verify=False,
                 same_host=False, same_domain=True):
        self.max_depth = max_depth
        self.max_count = max_count
        self.concurrency = concurrency
        self.timeout = timeout
        self.time = time
        self.headers = self.default_headers
        self.headers.update(headers or {})
        self.cookies = self.default_cookies
        self.cookies.update(cookies or {})
        self.ssl_verify = ssl_verify
        self.same_host = same_host
        self.same_domain = same_domain


class UrlObj(object):

    def __init__(self, url, depth=0):
        if not url.startswith(("http", "https")):
            url = "http://" + url
        self.url = url.strip('/')
        self.depth = depth

    def __str__(self):
        return self.url

    def __repr__(self):
        return "<Url Object: %s>" % self.url

    def __hash__(self):
        return hash(self.url)


class UrlTable(object):

    infinite = float("inf")

    def __init__(self, size=0):
        self._urls = {}

        if size == 0:
            size = self.infinite
        self.size = size

    def __len__(self):
        return len(self._urls)

    def __contains__(self, url):
        return hash(url) in self._urls.keys()

    def __iter__(self):
        for url in self.urls:
            yield url

    def insert(self, url):
        if isinstance(url, basestring):
            url = UrlObj(url)
        if UrlObj not in self:
            self._urls.setdefault(hash(url), url)

    @property
    def urls(self):
        return self._urls.values()

    def full(self):
        return len(self) >= self.size


class Spider(object):

    logger = logging.getLogger("spider")

    def __init__(self, strategy=Strategy()):
        monkey.patch_all()
        self.strategy = strategy
        self.queue = queue.Queue()
        self.urltable = UrlTable(strategy.max_count)
        self.pool = pool.Pool(strategy.concurrency)
        self.greenlet_finished = event.Event()
        self._stop = event.Event()

    def setRootUrl(self, url):
        if isinstance(url, basestring):
            url = UrlObj(url)
        self.root = url
        self.put(self.root)

    def put(self, url):
        if url not in self.urltable:
            self.queue.put(url)

    def run(self):
        self.timer = Timer(self.strategy.time, self.stop)
        self.timer.start()
        self.logger.info("Spider '%s' start running", self.root)

        while not self.stopped() and self.timer.is_alive():
            for greenlet in list(self.pool):
                if greenlet.dead:
                    self.pool.discard(greenlet)
            try:
                url = self.queue.get_nowait()
            except queue.Empty:
                if self.pool.free_count() != self.pool.size:
                    self.greenlet_finished.wait()
                    self.greenlet_finished.clear()
                    continue
                else:
                    self.stop()
            greenlet = Handler(url, self)
            self.pool.start(greenlet)

    def stopped(self):
        return self._stop.is_set()

    def stop(self):
        self.logger.info("Spider '%s' finished. Fetch (%d) urls.", self.root, len(self.urltable))  # noqa
        self.timer.cancel()
        self._stop.set()
        self.pool.join()
        self.queue.put(StopIteration)
        return


class Handler(gevent.Greenlet):

    logger = logging.getLogger("handler")

    def __init__(self, urlobj, spider):
        gevent.Greenlet.__init__(self)
        self.urlobj = urlobj
        self.spider = spider

    def _run(self):
        strategy = self.spider.strategy
        urltable = self.spider.urltable
        queue = self.spider.queue

        try:
            html = self.open(self.urlobj.url)
        except Exception, why:
            self.logger.debug("Open '%s' failed: %s", self.urlobj, why)
            return self.stop()

        depth = self.urlobj.depth + 1

        if strategy.max_depth and (depth > strategy.max_depth):
            return self.stop()

        for link in self.feed(html):

            if urltable.full():
                self.stop()
                self.spider.stop()
                return

            if link in urltable:
                continue

            if strategy.same_host and (not UrlFilter.isSameHost(link, self.urlobj.url)):  # noqa
                continue

            if strategy.same_domain and (not UrlFilter.isSameDomain(link, self.urlobj.url)):  # noqa
                continue

            url = UrlObj(link, depth)
            urltable.insert(url)
            queue.put(url)

            self.logger.debug("Crawled (%d) urls for '%s'.", len(urltable), url)  # noqa

        self.stop()

    def open(self, url):
        strategy = self.spider.strategy
        try:
            resp = requests.get(url,
                                headers=strategy.headers,
                                cookies=strategy.cookies,
                                timeout=strategy.timeout,
                                verify=strategy.ssl_verify)
        except requests.exceptions.RequestException, e:
            raise e
        if resp.status_code != requests.codes.ok:
            resp.raise_for_status()
        if resp.encoding is None:
            charset = HtmlAnalyzer.detectCharSet(resp.text)
            if charset is None:
                resp.encoding = 'utf-8'
            else:
                resp.encoding = charset
        return resp.text

    def feed(self, html):
        return HtmlAnalyzer.extractLinks(html, self.urlobj.url)

    def stop(self):
        self.spider.greenlet_finished.set()
        self.kill(block=False)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG if "-v" in sys.argv else logging.WARN,
        format='<%(asctime)s> [%(levelname)s] %(message)s',
        datefmt='%Y:%m:%d %H:%M:%S')
    root = 'http://ast.sina.cn'
    spider = Spider()
    spider.setRootUrl(root)
    spider.run()
