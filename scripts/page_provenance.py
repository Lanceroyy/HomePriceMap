"""Modification evidence for generated HTML, not fetch or filesystem dates.

The builders run sequentially and persist this ledger with their pages. A first
unchanged observation has no known modification date. Only an actual content
write can establish one; sitemap readers recheck the fingerprint before use.
"""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile


def _valid_date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    if parsed.isoformat() != value or parsed > datetime.now(timezone.utc).date():
        return None
    return value


def _fingerprint(content):
    # Checkout/platform line endings are not a new housing-content revision.
    return hashlib.sha256(content.replace(b'\r\n', b'\n').replace(b'\r', b'\n')).hexdigest()


class PageProvenance:
    def __init__(self, root, written_on=None):
        self.root = Path(root).resolve()
        self.path = self.root / 'data' / 'sitemap_page_provenance.json'
        self.written_on = written_on
        self.pages = {}
        self.dirty = False
        try:
            state = json.loads(self.path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
            return
        if (isinstance(state, dict) and type(state.get('version')) is int
                and state['version'] == 1 and isinstance(state.get('pages'), dict)):
            self.pages = state['pages']

    def _key(self, path):
        return Path(path).resolve().relative_to(self.root).as_posix()

    def _date_for(self, key, digest):
        record = self.pages.get(key)
        if isinstance(record, dict) and record.get('sha256') == digest:
            return _valid_date(record.get('lastmod'))
        return None

    def write(self, path, html):
        path = Path(path)
        key = self._key(path)
        digest = _fingerprint(html.encode('utf-8'))
        try:
            previous = _fingerprint(path.read_bytes())
        except FileNotFoundError:
            previous = None
        if previous == digest:
            stamp = self._date_for(key, digest)
        else:
            # Record only after a successful real write, never a daily no-op.
            path.write_text(html, encoding='utf-8', newline='\n')
            record = self.pages.get(key)
            restoring = (previous is None and isinstance(record, dict)
                         and record.get('sha256') == digest)
            # Recreating absent output from a matching prior receipt is not
            # new content. Preserve even an unknown date through clean builds.
            if restoring:
                stamp = self._date_for(key, digest)
            else:
                # A long run can cross UTC midnight; date the write, not init.
                stamp = _valid_date(datetime.now(timezone.utc).date().isoformat()
                                    if self.written_on is None else self.written_on)
        record = {'sha256': digest, 'lastmod': stamp}
        if self.pages.get(key) != record:
            self.pages[key] = record
            self.dirty = True

    def lastmod_for(self, path):
        try:
            key = self._key(path)
            digest = _fingerprint(Path(path).read_bytes())
        except (FileNotFoundError, ValueError):
            return None
        return self._date_for(key, digest)

    def retain(self, paths):
        keys = {self._key(path) for path in paths if Path(path).is_file()}
        retained = {key: value for key, value in self.pages.items() if key in keys}
        if retained != self.pages:
            self.pages = retained
            self.dirty = True

    def save(self):
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({'version': 1, 'pages': self.pages}, sort_keys=True, indent=2) + '\n'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                             dir=self.path.parent, prefix='.page-provenance-',
                                             suffix='.tmp', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
            temporary.replace(self.path)
            self.dirty = False
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
