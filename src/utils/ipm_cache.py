# src/utils/ipm_cache.py

import hashlib
from functools import lru_cache
from typing import Union, Optional
from src.models.ipm import IPMFile
from src.utils.ipm_parser import parse_ipm_file

def _hash(text: str) -> str:
    """Return a 40-char SHA-1 hex digest."""
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()

@lru_cache(maxsize=128)                 # one object per unique key
def _parse_cached(key: str, text: str) -> IPMFile:
    # key is only here to make lru_cache key = (key, text_hash) unique
    return parse_ipm_file(text)

def get_ipm(ipm_data: Union[str, IPMFile], ipm_id: Optional[str] = None) -> IPMFile:
    """
    Return an IPMFile, using an in-process cache.

    Parameters
    ----------
    ipm_data : str | IPMFile
        Raw IPM text or an already-parsed object.
    ipm_id : str | None
        Optional *stable* identifier supplied by the caller
        (e.g. filename, UUID).  If omitted we hash the text.

    Notes
    -----
    • Two different files with the same id *and* identical content
      hit the same cache line (safe).<br>
    • Two different files with the same id but *different* content
      will **overwrite** each other **— therefore only pass `ipm_id`
      if you guarantee uniqueness**.  Otherwise leave it `None`.
    """
    if isinstance(ipm_data, IPMFile):
        return ipm_data

    if ipm_id is None:
        key = _hash(ipm_data)
    else:
        key = f"{ipm_id}:{_hash(ipm_data)}"   # protects against id-clashes

    return _parse_cached(key, ipm_data)