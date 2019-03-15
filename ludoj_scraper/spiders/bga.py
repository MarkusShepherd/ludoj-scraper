# -*- coding: utf-8 -*-

''' Board Game Atlas spider '''

from functools import partial
from itertools import chain
from urllib.parse import urlencode

from scrapy import Request, Spider
from scrapy.utils.project import get_project_settings

from ..items import GameItem, RatingItem
from ..loaders import GameJsonLoader, RatingJsonLoader
from ..utils import extract_bga_id, now, parse_float, parse_json

API_URL = 'https://www.boardgameatlas.com/api'


def _json_from_response(response):
    result = parse_json(response.text) if hasattr(response, 'text') else None
    return result or {}


def _extract_meta(response=None):
    if hasattr(response, 'meta') and response.meta:
        return response.meta
    if hasattr(response, 'request') and hasattr(response.request, 'meta'):
        return response.request.meta or {}
    return {}


def _extract_item(item=None, response=None, item_cls=GameItem):
    if item:
        return item
    meta = _extract_meta(response)
    return meta.get('item') or item_cls()


def _extract_url(item=None, response=None, default=None):
    if item and item.get('url'):
        return item['url']
    meta = _extract_meta(response)
    if meta.get('url'):
        return meta['url']
    if hasattr(response, 'url') and response.url:
        return response.url
    if hasattr(response, 'request') and hasattr(response.request, 'url'):
        return response.request.url
    return default


def _extract_bga_id(item=None, response=None):
    if item and item.get('bga_id'):
        return item['bga_id']
    meta = _extract_meta(response)
    if meta.get('bga_id'):
        return meta['bga_id']
    url = _extract_url(item, response)
    return extract_bga_id(url)


def _extract_requests(response=None):
    meta = _extract_meta(response)
    return meta.get('game_requests')


class BgaSpider(Spider):
    ''' Board Game Atlas spider '''

    name = 'bga'
    allowed_domains = ('boardgameatlas.com',)
    item_classes = (GameItem, RatingItem)
    api_url = API_URL
    expected_items = 27_500
    expected_reviews = 35_000

    custom_settings = {
        'IMAGES_URLS_FIELD': None,
        'DOWNLOAD_DELAY': 10,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1,
    }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        ''' initialise spider from crawler '''

        kwargs.setdefault('settings', crawler.settings)
        spider = cls(*args, **kwargs)
        spider._set_crawler(crawler)
        return spider

    def __init__(self, *args, settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        settings = settings or get_project_settings()
        self.client_id = settings.get('BGA_CLIENT_ID')
        self.scrape_images = settings.getbool('BGA_SCRAPE_IMAGES')
        self.scrape_videos = settings.getbool('BGA_SCRAPE_VIDEOS')
        self.scrape_reviews = settings.getbool('BGA_SCRAPE_REVIEWS')

    def _api_url(self, path='search', query=None):
        query = query or {}
        query.setdefault('client_id', self.client_id)
        query.setdefault('limit', 100)
        return '{}/{}?{}'.format(
            self.api_url, path, urlencode(sorted(query.items(), key=lambda x: x[0])))

    def _game_requests(self, bga_id):
        if self.scrape_images:
            yield self._api_url('game/images', {'game-id': bga_id}), self.parse_images
        if self.scrape_videos:
            yield self._api_url('game/videos', {'game-id': bga_id}), self.parse_videos
        if self.scrape_reviews:
            yield self._api_url('game/reviews', {'game-id': bga_id}), self.parse_reviews

    # pylint: disable=no-self-use
    def _next_request_or_item(self, item, requests):
        if not requests:
            return item

        url, callback = requests.pop(0)
        callback = partial(callback, item=item)
        return Request(
            url=url,
            callback=callback,
            errback=callback,
            meta={'item': item, 'game_requests': requests},
        )

    def start_requests(self):
        ''' generate start requests '''

        for page in range(self.expected_items * 21 // 2000):
            query = {
                'order-by': 'popularity',
                'skip': page * 100,
            }
            yield Request(self._api_url(query=query), callback=self.parse)

        for page in range(self.expected_reviews * 21 // 2000):
            query = {'skip': page * 100}
            yield Request(
                self._api_url(path='reviews', query=query),
                callback=self.parse_user_reviews,
            )

    # pylint: disable=line-too-long
    def parse(self, response):
        '''
        @url https://www.boardgameatlas.com/api/search?client_id=SB1VGnDv7M&order-by=popularity&limit=100
        @returns items 100 100
        @returns requests 0 0
        @scrapes name description url image_url bga_id scraped_at worst_rating best_rating
        '''

        result = _json_from_response(response)
        games = result.get('games') or ()
        scraped_at = now()

        for game in games:
            bga_id = game.get('id') or extract_bga_id(game.get('url'))
            ldr = GameJsonLoader(
                item=GameItem(
                    bga_id=bga_id,
                    scraped_at=scraped_at,
                    worst_rating=1,
                    best_rating=5,
                ),
                json_obj=game,
                response=response,
            )

            ldr.add_jmes('name', 'name')
            ldr.add_jmes('alt_name', 'names')
            ldr.add_jmes('year', 'year_published')
            ldr.add_jmes('description', 'description_preview')
            ldr.add_jmes('description', 'description')

            ldr.add_jmes('designer', 'designers')
            ldr.add_jmes('artist', 'artists')
            ldr.add_jmes('publisher', 'primary_publisher')
            ldr.add_jmes('publisher', 'publishers')

            ldr.add_jmes('url', 'url')
            ldr.add_jmes('image_url', 'image_url')
            ldr.add_jmes('image_url', 'thumb_url')

            list_price = ldr.get_jmes('msrp')
            list_price = map('USD{:.2f}'.format, filter(None, map(parse_float, list_price)))
            ldr.add_value('list_price', list_price)

            ldr.add_jmes('min_players', 'min_players')
            ldr.add_jmes('max_players', 'max_players')
            ldr.add_jmes('min_age', 'min_age')
            ldr.add_jmes('min_time', 'min_playtime')
            ldr.add_jmes('max_time', 'max_playtime')

            item = ldr.load_item()
            requests = list(self._game_requests(bga_id))
            yield self._next_request_or_item(item, requests)

    def parse_images(self, response, item=None):
        '''
        @url https://www.boardgameatlas.com/api/game/images?client_id=SB1VGnDv7M&game-id=OIXt3DmJU0&limit=100
        @returns items 1 1
        @returns requests 0 0
        @scrapes image_url
        '''

        item = _extract_item(item, response)
        result = _json_from_response(response)

        ldr = GameJsonLoader(item=item, json_obj=result, response=response)
        ldr.add_value('image_url', item.get('image_url'))
        ldr.add_jmes('image_url', 'images[].url')
        ldr.add_jmes('image_url', 'images[].thumb')

        item = ldr.load_item()
        requests = _extract_requests(response)
        return self._next_request_or_item(item, requests)

    def parse_videos(self, response, item=None):
        '''
        @url https://www.boardgameatlas.com/api/game/videos?client_id=SB1VGnDv7M&game-id=OIXt3DmJU0&limit=100
        @returns items 1 1
        @returns requests 0 0
        @scrapes video_url
        '''

        item = _extract_item(item, response)
        result = _json_from_response(response)

        ldr = GameJsonLoader(item=item, json_obj=result, response=response)
        ldr.add_value('video_url', item.get('video_url'))
        ldr.add_jmes('video_url', 'videos[].url')

        item = ldr.load_item()
        requests = _extract_requests(response)
        return self._next_request_or_item(item, requests)

    # pylint: disable=no-self-use
    def parse_reviews(self, response, item=None):
        '''
        @url https://www.boardgameatlas.com/api/game/reviews?client_id=SB1VGnDv7M&game-id=OIXt3DmJU0&limit=100
        @returns items 1 1
        @returns requests 0 0
        @scrapes review_url
        '''

        item = _extract_item(item, response)
        result = _json_from_response(response)

        ldr = GameJsonLoader(item=item, json_obj=result, response=response)
        ldr.add_value('review_url', item.get('review_url'))
        ldr.add_jmes('review_url', 'reviews[].url')

        item = ldr.load_item()
        requests = _extract_requests(response)
        return self._next_request_or_item(item, requests)

    def parse_user_reviews(self, response):
        '''
        @url https://www.boardgameatlas.com/api/reviews?client_id=SB1VGnDv7M&limit=100
        @returns items 100 100
        @returns requests 0 0
        @scrapes bga_id bga_user_id bga_user_name
        '''

        result = _json_from_response(response)
        reviews = result.get('reviews') or ()
        scraped_at = now()

        for review in reviews:
            ldr = RatingJsonLoader(
                item=RatingItem(scraped_at=scraped_at),
                json_obj=review,
                response=response,
            )

            ldr.add_jmes('bga_id', 'game.id.objectId')
            ldr.add_jmes('bga_user_id', 'user.id')
            ldr.add_jmes('bga_user_name', 'user.username')
            ldr.add_jmes('bga_user_rating', 'rating')
            comments = chain(ldr.get_jmes('title'), ldr.get_jmes('description'))
            ldr.add_value('comment', '\n'.join(filter(None, comments)))

            yield ldr.load_item()
