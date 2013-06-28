#-*- coding: utf-8 -*-

import re
import urllib
import domain
import urlparse
from pyquery import PyQuery


class HtmlAnalyzer(object):

    # pyquery use lxml, lxml has bug when handle xml with encoding.
    # so remove encoding='xxx' before PyQuery handle it.
    @staticmethod
    def _removeEncoding(xml):
        encoding_xml = re.compile(r'^(\s*<\?xml\s+.*)encoding=.*(\?>)', re.UNICODE)  # noqa
        if encoding_xml.match(xml):
            xml = encoding_xml.sub(r'\1\2', xml)
        return xml

    @staticmethod
    def detectCharSet(html):

        pq = PyQuery(HtmlAnalyzer._removeEncoding(html))
        metas = pq('head')('meta')

        for meta in metas:
            for key in meta.keys():
                if key == "charset":
                    charset = meta.get('charset')
                    return charset
                if key == "content":
                    try:
                        p = re.match(r".+charset=(.*)\W*", meta.get('content'))
                        return p.group(1)
                    except:
                        continue

    @staticmethod
    def extractLinks(html, baseurl):

        def _extract(url, attr):
            link = url.attrib[attr]

            if link is None:
                raise

            # strip('\\"') for href like
            # <a href=\"http://www.sina.com.cn\">Sina</a>
            link = link.strip("/ ").strip('\\"')

            link = urlparse.urljoin(baseurl, link)
            link = urlparse.urldefrag(link)[0]

            try:
                link = link.encode('utf-8')
            except:
                raise

            try:
                link = urllib.quote(link, ':?=+&#/@')
            except (UnicodeDecodeError, KeyError):
                pass

            return link

        def _isValidLink(url):
            try:
                return all([UrlFilter.checkScheme(url),
                            UrlFilter.checkInvalidChar(url),
                            UrlFilter.checkInvalidExtention(url)])
            except:
                return False

        pq = PyQuery(HtmlAnalyzer._removeEncoding(html))

        allLinks = []

        for url in pq('a'):
            try:
                link = _extract(url, 'href')
            except:
                continue
            if _isValidLink(link):
                allLinks.append(link)

        for url in pq('form'):
            try:
                link = _extract(url, 'action')
            except:
                continue
            if _isValidLink(link):
                allLinks.append(link)
        return allLinks


class UrlFilter(object):

    invalid_chars = {'\'': None,
                     '\"': None,
                     '\\': None,
                     ' ': None,
                     '\n': None,
                     '\r': None,
                     '+': None
                     }

    invalid_extention = {
        'jpg':  None,
        'gif':  None,
        'bmp':  None,
        'jpeg':  None,
        'png':  None,

        'swf':  None,
        'mp3':  None,
        'wma':  None,
        'wmv':  None,
        'wav':  None,
        'mid':  None,
        'ape':  None,
        'mpg':  None,
        'mpeg':  None,
        'rm':  None,
        'rmvb':  None,
        'avi':  None,
        'mkv':  None,

        'zip':  None,
        'rar':  None,
        'gz':  None,
        'iso':  None,
        'jar':  None,

        'doc':  None,
        'docx':  None,
        'ppt':  None,
        'pptx':  None,
        'chm':  None,
        'pdf':  None,

        'exe':  None,
        'msi':  None,
    }

    @classmethod
    def checkInvalidChar(cls, url):
        exist_invalid_char = False
        for c in url:
            if c in cls.invalid_chars:
                exist_invalid_char = True
                break
        return (not exist_invalid_char)

    @classmethod
    def checkInvalidExtention(cls, url):
        dotpos = url.rfind('.') + 1
        typestr = url[dotpos:].lower()
        return (typestr not in cls.invalid_extention)

    @staticmethod
    def checkScheme(url):
        scheme, netloc, path, pm, q, f = urlparse.urlparse(url)
        return scheme in ('http', 'https')

    @staticmethod
    def isSameDomain(first_url, second_url):
        fhost = urlparse.urlparse(first_url).netloc
        shost = urlparse.urlparse(second_url).netloc
        return (domain.GetFirstLevelDomain(fhost) ==
                domain.GetFirstLevelDomain(shost))

    @staticmethod
    def isSameHost(first_url, second_url):
        return urlparse.urlparse(first_url).netloc == urlparse.urlparse(second_url).netloc  # noqa

    @staticmethod
    def isSameSuffixWithoutWWW(first_url, second_url):
        fhost = '.' + urlparse.urlparse(first_url).netloc
        shost = '.' + urlparse.urlparse(second_url).netloc

        if shost[:5] == '.www.':
            shost = shost[5:]

        if fhost.find(shost) != -1:
            return True
        else:
            return False

    # check whether first_url has the suffix second_url
    @staticmethod
    def isSameSuffix(first_url, second_url):
        fhost = '.' + urlparse.urlparse(first_url).netloc
        shost = '.' + urlparse.urlparse(second_url).netloc

        if fhost.find(shost) != -1:
            return True
        else:
            return False
