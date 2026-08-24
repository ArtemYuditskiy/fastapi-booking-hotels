from typing import Annotated

from fastapi import Depends

from app.catalog.cache import CatalogCache, RedisCatalogCache
from app.redis_client import redis_client


def get_catalog_cache() -> CatalogCache:
    return RedisCatalogCache(redis_client)


CatalogCacheDependency = Annotated[CatalogCache, Depends(get_catalog_cache)]
