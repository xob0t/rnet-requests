"""
rnet_requests.structures
~~~~~~~~~~~~~~~~~~~~~~~~

Data structures that power rnet-requests.
"""

from collections.abc import Iterator, MutableMapping
from typing import Any


class CaseInsensitiveDict(MutableMapping):
    """A case-insensitive ``dict``-like object.

    Implements all methods and operations of
    ``MutableMapping`` as well as dict's ``copy``. Also
    provides ``lower_items``.

    All keys are expected to be strings. The structure remembers the
    case of the last key to be set, and ``iter(instance)``,
    ``keys()``, ``items()``, ``iterkeys()``, and ``iteritems()``
    will contain case-sensitive keys. However, querying and contains
    testing is case insensitive::

        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['accept'] == 'application/json'  # True
        list(cid) == ['Accept']  # True

    For example, ``headers['content-encoding']`` will return the
    value of a ``'Content-Encoding'`` response header, regardless
    of how the header name was originally stored.

    If the constructor, ``.update``, or equality comparison
    operations are given keys that have equal ``.lower()``s, the
    behavior is undefined.
    """

    def __init__(self, data: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self._store: dict[str, tuple[str, Any]] = {}
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        # Use the lowercased key for lookups, but store the actual
        # key alongside the value.
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key: str) -> Any:
        return self._store[key.lower()][1]

    def __delitem__(self, key: str) -> None:
        del self._store[key.lower()]

    def __iter__(self) -> Iterator[str]:
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    def lower_items(self) -> Iterator[tuple[str, Any]]:
        """Like iteritems(), but with all lowercase keys."""
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, MutableMapping):
            other = CaseInsensitiveDict(dict(other))
        else:
            return NotImplemented
        # Compare insensitively
        return dict(self.lower_items()) == dict(other.lower_items())

    # Copy is required
    def copy(self) -> "CaseInsensitiveDict":
        return CaseInsensitiveDict({k: v for k, v in self.items()})

    def __repr__(self) -> str:
        return str(dict(self.items()))


class LookupDict(dict):
    """Dictionary lookup object."""

    def __init__(self, name: str | None = None) -> None:
        self.name = name
        super().__init__()

    def __repr__(self) -> str:
        return f"<lookup '{self.name}'>"

    def __getitem__(self, key: str) -> Any:
        # We allow fall-through here, so values default to None
        return self.__dict__.get(key, None)

    def get(self, key: str, default: Any | None = None) -> Any:
        return self.__dict__.get(key, default)
