# -*- coding: utf-8 -*-

''' Scrapy items '''

import csv
import logging

from datetime import date, datetime
from functools import partial

from scrapy import Field, Item
from scrapy.loader.processors import Identity, MapCompose
from w3lib.html import remove_tags, replace_entities

from .utils import (
    clear_list, identity, normalize_space, now, parse_bool, parse_date, parse_float,
    parse_int, parse_json, serialize_date, serialize_json, smart_walks, validate_range)

IDENTITY = Identity()
LOGGER = logging.getLogger(__name__)
POS_INT_PROCESSOR = MapCompose(
    identity, str, remove_tags, replace_entities, replace_entities, normalize_space,
    parse_int, partial(validate_range, lower=1))
NN_INT_PROCESSOR = MapCompose(
    identity, str, remove_tags, replace_entities, replace_entities, normalize_space,
    parse_int, partial(validate_range, lower=0))
POS_FLOAT_PROCESSOR = MapCompose(
    identity, str, remove_tags, replace_entities, replace_entities, normalize_space,
    parse_float, partial(validate_range, lower=0), lambda v: v or None)
NN_FLOAT_PROCESSOR = MapCompose(
    identity, str, remove_tags, replace_entities, replace_entities, normalize_space,
    parse_float, partial(validate_range, lower=0))


def _serialize_bool(item):
    return int(item) if isinstance(item, bool) else None


class TypedItem(Item):
    ''' Item with typed fields '''

    def __setitem__(self, key, value):
        field = self.fields.get(key) or {}
        setter = field.get('setter', IDENTITY)

        super().__setitem__(key, setter(value))

        dtype = field.get('dtype')
        convert = field.get('dtype_convert')

        if self[key] is None or dtype is None or isinstance(self[key], dtype):
            return

        if not convert:
            raise ValueError(
                f'field <{key}> requires type {dtype} but found type {type(self[key])}')

        convert = convert if callable(convert) else dtype[0] if isinstance(dtype, tuple) else dtype
        value = convert(self[key])

        assert isinstance(value, dtype) or value is None

        super().__setitem__(key, setter(value))

    @classmethod
    def parse(cls, item):
        ''' parses the fields in a dict-like item and returns a TypedItem '''

        article = cls()

        for key, properties in cls.fields.items():
            value = item.get(key)

            if value is None or value == '':
                continue

            try:
                article[key] = value
                continue

            except ValueError:
                pass

            parser = properties.get('parser', IDENTITY)
            article[key] = parser(value)

        return article

    @classmethod
    def clean(cls, item):
        ''' cleans the fields in a dict-like item and returns a TypedItem '''

        return cls({k: v for k, v in item.items() if v and k in cls.fields})

    @classmethod
    def from_csv(cls, *paths, **kwargs):
        ''' find CSV files and and parse contents to items '''

        try:
            from smart_open import smart_open
        except ImportError:
            LOGGER.exception('<smart_open> needs to be importable')
            return

        kwargs['load'] = False
        kwargs.setdefault('accept_path', lambda path: path and path.lower().endswith('.csv'))

        for path, _ in smart_walks(*paths, **kwargs):
            LOGGER.info('parsing items from %s...', path)

            with smart_open(path, 'r') as csv_file:
                reader = csv.DictReader(csv_file)
                yield from map(cls.parse, reader)


class GameItem(TypedItem):
    ''' item representing a game '''

    name = Field(dtype=str, required=True)
    alt_name = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    year = Field(
        dtype=int,
        dtype_convert=parse_int,
        input_processor=MapCompose(
            identity, str, remove_tags, replace_entities, replace_entities, normalize_space,
            parse_int, partial(validate_range, lower=-4000, upper=date.today().year + 10),
            lambda year: year or None),
        default=None,
    )
    game_type = Field(dtype=str)
    description = Field(
        dtype=str,
        input_processor=MapCompose(
            remove_tags, replace_entities, replace_entities,
            partial(normalize_space, preserve_newline=True)),
    )

    designer = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    artist = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    publisher = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )

    url = Field(dtype=str)
    image_url = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    video_url = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    external_link = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    list_price = Field(dtype=str) # currency?

    min_players = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    max_players = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    min_players_rec = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    max_players_rec = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    min_players_best = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    max_players_best = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    min_age = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    max_age = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    min_age_rec = Field(
        dtype=float, dtype_convert=parse_float,
        input_processor=POS_FLOAT_PROCESSOR, default=None)
    max_age_rec = Field(
        dtype=float, dtype_convert=parse_float,
        input_processor=POS_FLOAT_PROCESSOR, default=None)
    min_time = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    max_time = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)

    category = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    mechanic = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    cooperative = Field(
        dtype=bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    compilation = Field(
        dtype=bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    family = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    expansion = Field(
        dtype=list,
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )
    implementation = Field(
        dtype=list,
        input_processor=MapCompose(parse_int),
        output_processor=clear_list,
        serializer=serialize_json,
        parser=parse_json,
    )

    rank = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    num_votes = Field(
        dtype=int, dtype_convert=parse_int, input_processor=NN_INT_PROCESSOR, default=0)
    avg_rating = Field(
        dtype=float, dtype_convert=parse_float, input_processor=POS_FLOAT_PROCESSOR, default=None)
    stddev_rating = Field(
        dtype=float, dtype_convert=parse_float, input_processor=NN_FLOAT_PROCESSOR, default=None)
    bayes_rating = Field(
        dtype=float, dtype_convert=parse_float, input_processor=POS_FLOAT_PROCESSOR, default=None)
    worst_rating = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    best_rating = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)

    complexity = Field(
        dtype=float, dtype_convert=parse_float, input_processor=POS_FLOAT_PROCESSOR, default=None)
    easiest_complexity = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    hardest_complexity = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    language_dependency = Field(
        dtype=float, dtype_convert=parse_float, input_processor=POS_FLOAT_PROCESSOR, default=None)
    lowest_language_dependency = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    highest_language_dependency = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)

    bgg_id = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    freebase_id = Field(dtype=str)
    wikidata_id = Field(dtype=str)
    wikipedia_id = Field(dtype=str)
    dbpedia_id = Field(dtype=str)
    luding_id = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)

    published_at = Field(dtype=datetime, serializer=serialize_date, parser=parse_date)
    updated_at = Field(dtype=datetime, serializer=serialize_date, parser=parse_date)
    scraped_at = Field(
        dtype=datetime,
        required=True,
        default=now,
        serializer=serialize_date,
        parser=parse_date,
    )


class RatingItem(TypedItem):
    ''' item representing a rating '''

    bgg_id = Field(dtype=int, dtype_convert=parse_int, required=True)
    bgg_user_name = Field(dtype=str, required=True)

    bgg_user_rating = Field(
        dtype=float, dtype_convert=parse_float, input_processor=POS_FLOAT_PROCESSOR, default=None)
    bgg_user_owned = Field(
        dtype=bool,
        dtype_convert=parse_bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    bgg_user_prev_owned = Field(
        dtype=bool,
        dtype_convert=parse_bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    bgg_user_for_trade = Field(
        dtype=bool,
        dtype_convert=parse_bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    bgg_user_want_in_trade = Field(
        dtype=bool,
        dtype_convert=parse_bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    bgg_user_want_to_play = Field(
        dtype=bool,
        dtype_convert=parse_bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    bgg_user_want_to_buy = Field(
        dtype=bool,
        dtype_convert=parse_bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    bgg_user_preordered = Field(
        dtype=bool,
        dtype_convert=parse_bool,
        default=None,
        input_processor=IDENTITY,
        serializer=_serialize_bool,
        parser=parse_bool,
    )
    bgg_user_wishlist = Field(
        dtype=int, dtype_convert=parse_int, input_processor=POS_INT_PROCESSOR, default=None)
    bgg_user_play_count = Field(
        dtype=int, dtype_convert=parse_int, input_processor=NN_INT_PROCESSOR, default=0)

    published_at = Field(dtype=datetime, serializer=serialize_date, parser=parse_date)
    updated_at = Field(dtype=datetime, serializer=serialize_date, parser=parse_date)
    scraped_at = Field(
        dtype=datetime,
        required=True,
        default=now,
        serializer=serialize_date,
        parser=parse_date,
    )
