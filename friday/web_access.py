"""Small, bounded public-web reader. No browser cookies or local files are sent."""
import ipaddress
import re
import socket
import threading
import time
from urllib.parse import urlparse, urljoin, parse_qs, urlencode
from xml.etree import ElementTree

import requests
from lxml import html


class Cancelled(Exception):
    pass


def public_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('Некорректная ссылка.')
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Разрешены только публичные ссылки http/https без пароля.')
    if parsed.port not in (None, 80, 443):
        raise ValueError('Для веб-страниц разрешены порты 80 и 443.')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Доступ к локальным и служебным сетевым адресам запрещён.')
    return value


class WebAccess:
    MAX_BYTES = 1_500_000

    def __init__(self, cancel=None):
        self.cancel = cancel or threading.Event()
        self.cache = {}

    def check(self):
        if self.cancel.is_set():
            raise Cancelled('Задача остановлена.')

    def fetch(self, url):
        started = time.monotonic()
        for _ in range(5):
            self.check(); public_url(url)
            session = requests.Session(); session.trust_env = False
            with session.get(url, timeout=(5, 12), allow_redirects=False, stream=True,
                              headers={'User-Agent':'FridayAssistant/1.0 (public page reader)',
                                       'Accept':'text/html,application/rss+xml,application/xml,text/plain',
                                       'Accept-Language':'ru,en;q=0.7'}) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get('Location', '')); continue
                response.raise_for_status()
                mime = response.headers.get('Content-Type', '').split(';')[0].lower()
                if mime and not any(kind in mime for kind in ('html', 'xml', 'text/plain')):
                    raise ValueError('Этот формат страницы не поддерживается; доступны HTML и текст.')
                data = bytearray()
                for chunk in response.iter_content(16384):
                    self.check()
                    if time.monotonic()-started > 30:
                        raise TimeoutError('Истекло время загрузки страницы.')
                    data.extend(chunk)
                    if len(data) > self.MAX_BYTES:
                        raise ValueError('Страница слишком большая для быстрого чтения.')
                return url, bytes(data), mime
        raise ValueError('Слишком много перенаправлений сайта.')

    def search(self, query):
        query = str(query).strip()
        if not query or len(query) > 500:
            raise ValueError('Укажите поисковый запрос до 500 символов.')
        key = ('search', query.casefold())
        cached = self.cache.get(key)
        if cached and time.monotonic()-cached[0] < 120:
            self.check(); return cached[1]
        errors = []
        # Bing can return an unrelated regional/portal page when the system
        # locale or VPN exit is unusual.  DuckDuckGo's HTML endpoint gives a
        # more stable set of ordinary web results for assistant queries.
        for provider in ('duckduckgo', 'bing'):
            try:
                if provider == 'bing':
                    _, body, _ = self.fetch('https://www.bing.com/search?' + urlencode({'q':query,'format':'rss'}))
                    root = ElementTree.fromstring(body)
                    results = [{'title':item.findtext('title',''), 'url':item.findtext('link',''),
                                'snippet':item.findtext('description','')[:900], 'date':item.findtext('pubDate','')}
                               for item in root.findall('./channel/item')]
                else:
                    _, body, _ = self.fetch('https://html.duckduckgo.com/html/?' + urlencode({'q':query}))
                    tree = html.fromstring(body)
                    results = []
                    for node in tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," result ")]'):
                        anchors = node.xpath('.//a[contains(@class,"result__a")]')
                        if not anchors:
                            continue
                        a = anchors[0]; target = urljoin('https://duckduckgo.com', a.get('href',''))
                        target = parse_qs(urlparse(target).query).get('uddg',[target])[0]
                        snippets = node.xpath('.//*[contains(@class,"result__snippet")]')
                        results.append({'title':a.text_content().strip(),'url':target,
                                        'snippet':snippets[0].text_content().strip()[:900] if snippets else '', 'date':''})
                seen = set(); clean = []
                for result in results:
                    parsed = urlparse(result['url'])
                    if parsed.scheme in ('http','https') and parsed.hostname and result['url'] not in seen:
                        seen.add(result['url']); clean.append(result)
                if not clean:
                    raise ValueError('Поисковик не вернул результаты или запросил проверку браузера.')
                value = {'query':query,'provider':provider,'results':clean[:5],
                         'retrieved_at':time.strftime('%Y-%m-%d %H:%M:%S'),
                         'notice':'Это выдержки поисковой выдачи, страницы ещё не прочитаны.'}
                self.cache[key] = (time.monotonic(), value)
                return value
            except Cancelled:
                raise
            except (requests.RequestException, ValueError, OSError, ElementTree.ParseError) as exc:
                errors.append(f'{provider}: {exc}')
        raise ValueError('Поиск недоступен. Проверьте интернет или попробуйте позже. ' + '; '.join(errors))

    def read(self, url):
        key = ('page', url); cached = self.cache.get(key)
        if cached and time.monotonic()-cached[0] < 120:
            self.check(); return cached[1]
        final, body, mime = self.fetch(url)
        if 'text/plain' in mime:
            title, text = final, body.decode('utf-8',errors='replace')
        else:
            tree = html.fromstring(body)
            title = ' '.join(tree.xpath('//title/text()')).strip() or urlparse(final).hostname
            for node in tree.xpath('//script|//style|//noscript|//nav|//footer|//header|//form|//svg'):
                node.drop_tree()
            main = tree.xpath('//main|//article')
            text = (main[0] if main else tree).text_content()
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) < 60:
            raise ValueError('Недостаточно доступного текста. Сайт может требовать JavaScript, вход или проверку браузера.')
        result = {'url':final,'title':title[:240],'text':text[:14000], 'truncated':len(text)>14000,
                  'retrieved_at':time.strftime('%Y-%m-%d %H:%M:%S')}
        self.cache[key] = (time.monotonic(),result)
        return result
