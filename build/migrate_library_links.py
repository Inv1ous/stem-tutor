"""Migrate historical Markdown asset links to canonical Library paths.

Dry-run is the default. Applying requires an explicit journal directory; exact
original Markdown bytes are archived and hashed before any note is replaced.
Only recognized link destinations are rewritten. Fenced code, prose, labels,
embeds, dimensions, and fragments are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
from urllib.parse import unquote


def _parts(value: str) -> list[str]:
    if (not isinstance(value, str) or not value or value.startswith('/')
            or '\\' in value or '\x00' in value
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ValueError('unsafe relative path')
    return value.split('/')


def _open_dir(root: Path, parts: list[str], *, create: bool = False) -> int:
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            if create:
                try:
                    os.mkdir(part, mode=0o755, dir_fd=fd)
                except FileExistsError:
                    pass
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except Exception:
        os.close(fd)
        raise


def _read(root: Path, relative: str) -> bytes:
    parts = _parts(relative)
    parent = _open_dir(root, parts[:-1])
    try:
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError(f'not a regular file: {relative}')
            with os.fdopen(fd, 'rb') as stream:
                fd = -1
                return stream.read()
        finally:
            if fd >= 0:
                os.close(fd)
    finally:
        os.close(parent)


def _atomic_compare_write(root: Path, relative: str, original: bytes, updated: bytes) -> None:
    parts = _parts(relative)
    parent = _open_dir(root, parts[:-1])
    temp = '.link-migrate-' + uuid.uuid4().hex
    try:
        current_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(current_fd, 'rb') as stream:
            current = stream.read()
        if hashlib.sha256(current).digest() != hashlib.sha256(original).digest():
            raise ValueError(f'note changed since planning: {relative}')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            # Compare again immediately before the atomic replacement.
            current_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            with os.fdopen(current_fd, 'rb') as stream:
                current = stream.read()
            if hashlib.sha256(current).digest() != hashlib.sha256(original).digest():
                raise ValueError(f'note changed before replacement: {relative}')
            os.replace(temp, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            try:
                os.unlink(temp, dir_fd=parent)
            except FileNotFoundError:
                pass
    finally:
        os.close(parent)


def _fence_lines(text: str) -> set[int]:
    """Return lines inside CommonMark-style fenced code blocks."""
    hidden: set[int] = set()
    fence_char = None
    fence_len = 0
    for i, line in enumerate(text.splitlines(keepends=True)):
        match = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence_char is None:
            if match:
                token = match.group(1)
                fence_char, fence_len = token[0], len(token)
                hidden.add(i)
        else:
            hidden.add(i)
            if re.match(r'^ {0,3}' + re.escape(fence_char) + '{' + str(fence_len) + r',}\s*(?:\r?\n)?$', line):
                fence_char = None
                fence_len = 0
    return hidden


def _split_fragment(target: str) -> tuple[str, str]:
    # Keep URL query/fragment suffix byte-for-byte; only the path is mapped.
    pos = min([p for p in (target.find('#'), target.find('?')) if p >= 0], default=len(target))
    return target[:pos], target[pos:]


def _rewrite_text(text: str, aliases: dict[str, str]) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    hidden = _fence_lines(text)
    changed = 0
    # Match wiki links and inline Markdown links/images. Link labels/title/size
    # are outside the captured destination and therefore preserved exactly.
    wiki = re.compile(r'(?P<open>!?\[\[)(?P<target>[^]|]+)(?P<tail>(?:\|[^]]*)?\]\])')
    markdown = re.compile(r'(?P<open>!?\[[^\]\n]*\]\()(?P<target><[^>\n]+>|(?:\\.|[^\s()])+(?:\([^()]*\)(?:\\.|[^\s()])*)*)(?P<tail>\s+(?:"[^"\n]*"|\'[^\'\n]*\'|\([^\)\n]*\))\s*)?(?P<close>\))')
    result=[]
    for i,line in enumerate(lines):
        if i in hidden:
            result.append(line); continue
        # Inline code spans are code, not link references. Temporarily mask
        # them so Markdown-looking examples remain literal.
        inline=[]
        def mask_code(m):
            inline.append(m.group(0))
            return f'\x01CODE{len(inline)-1}\x01'
        protected=re.sub(r'(?<!`)`+[^`\n]*?`+(?!`)',mask_code,line)
        def repl(m):
            nonlocal changed
            raw=m.group('target')
            wrapped=raw.startswith('<') and raw.endswith('>')
            target=raw[1:-1] if wrapped else raw
            path,suffix=_split_fragment(target)
            # Markdown destinations may escape spaces or parentheses; aliases
            # are literal catalog references, with URL-decoding as a fallback.
            canonical=aliases.get(path) or aliases.get(unquote(path))
            if canonical is None: return m.group(0)
            changed += 1
            new=canonical+suffix
            return m.group('open')+('<'+new+'>' if wrapped else new)+(m.groupdict().get('tail') or '')+m.groupdict().get('close','')
        protected=wiki.sub(repl,protected)
        protected=markdown.sub(repl,protected)
        for n,code in enumerate(inline):
            protected=protected.replace(f'\x01CODE{n}\x01',code)
        line=protected
        result.append(line)
    return ''.join(result),changed


def _catalog_aliases(vault: Path) -> dict[str, str]:
    catalog=json.loads(_read(vault,'Library/catalog.json'))
    if type(catalog.get('format_version')) is not int or catalog['format_version'] != 1 or not isinstance(catalog.get('assets'),dict):
        raise ValueError('unsupported asset catalog')
    result={}
    for aid,entry in catalog['assets'].items():
        if not isinstance(entry,dict): raise ValueError('invalid asset entry')
        canonical=entry.get('path'); digest=entry.get('sha256')
        parts=_parts(canonical)
        if len(parts)<2 or parts[0]!='Library' or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
            raise ValueError(f'invalid catalog record: {aid}')
        data=_read(vault,canonical)
        if hashlib.sha256(data).hexdigest()!=digest: raise ValueError(f'catalog digest mismatch: {canonical}')
        for alias in entry.get('aliases',[]):
            _parts(alias)
            if alias in result and result[alias]!=canonical: raise ValueError(f'ambiguous legacy alias: {alias}')
            result[alias]=canonical
        if canonical in result and result[canonical]!=canonical: raise ValueError(f'ambiguous canonical path: {canonical}')
        result[canonical]=canonical
    return result


def plan(vault: Path) -> dict:
    vault=vault.resolve(strict=True)
    aliases=_catalog_aliases(vault)
    edits=[]; errors=[]
    for directory,dirs,files in os.walk(vault,followlinks=False):
        base=Path(directory); relbase=base.relative_to(vault)
        dirs[:]=sorted(d for d in dirs if d not in ('Library','.tutor','event','state') and not d.startswith('.') and not (base/d).is_symlink())
        for name in sorted(files):
            path=base/name
            if path.is_symlink() or path.suffix.lower()!='.md' or name.startswith('.'):
                continue
            rel=(relbase/path.name).as_posix()
            try:
                original=_read(vault,rel)
                text=original.decode('utf-8')
                updated,count=_rewrite_text(text,aliases)
                encoded=updated.encode('utf-8')
                if count and encoded!=original:
                    edits.append({'path':rel,'sha256':hashlib.sha256(original).hexdigest(),
                                  'updated_sha256':hashlib.sha256(encoded).hexdigest(),
                                  'replacements':count,'original':original.hex(),'updated':encoded.hex()})
            except (ValueError,UnicodeDecodeError,OSError) as exc:
                errors.append({'path':rel,'error':str(exc)})
    return {'format_version':1,'vault':str(vault),'edits':edits,'errors':errors}


def _journal(vault: Path, journal: Path, edits: list[dict]) -> None:
    journal=journal.expanduser().absolute()
    journal.mkdir(parents=True,exist_ok=True)
    if journal.is_symlink(): raise ValueError('journal directory must not be a symlink')
    root=journal
    manifest=[]
    for idx,edit in enumerate(edits):
        backup=f'originals/{idx:04d}-{hashlib.sha256(edit["path"].encode()).hexdigest()[:12]}.md'
        data=bytes.fromhex(edit['original'])
        if hashlib.sha256(data).hexdigest()!=edit['sha256']: raise ValueError('invalid planned backup digest')
        _write_journal(root,backup,data)
        manifest.append({k:edit[k] for k in ('path','sha256','updated_sha256','replacements')} | {'backup':backup})
    payload={'format_version':1,'vault':str(vault),'edits':manifest}
    _write_journal(root,'journal.json',(json.dumps(payload,indent=2)+'\n').encode())


def _write_journal(root: Path, relative: str, data: bytes) -> None:
    parts=_parts(relative); parent=_open_dir(root,parts[:-1],create=True)
    temp='.journal-'+uuid.uuid4().hex
    try:
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        with os.fdopen(fd,'wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        try: os.link(temp,parts[-1],src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
        except FileExistsError:
            if _read(root,relative)!=data: raise ValueError(f'journal conflict: {relative}')
        os.fsync(parent)
    finally:
        try: os.unlink(temp,dir_fd=parent)
        except FileNotFoundError: pass
        os.close(parent)


def apply(report: dict, journal: Path) -> dict:
    if report.get('errors'): raise ValueError('plan has unresolved errors')
    vault=Path(report['vault'])
    if not report['edits']:
        return {'updated_files':0,'replacements':0,'journal':str(journal),'vault_files_deleted':0}
    _journal(vault,journal,report['edits'])
    changed=0
    for edit in report['edits']:
        original=bytes.fromhex(edit['original']); updated=bytes.fromhex(edit['updated'])
        if hashlib.sha256(original).hexdigest()!=edit['sha256'] or hashlib.sha256(updated).hexdigest()!=edit['updated_sha256']:
            raise ValueError(f'invalid plan digest: {edit["path"]}')
        _atomic_compare_write(vault,edit['path'],original,updated)
        changed+=1
    return {'updated_files':changed,'replacements':sum(x['replacements'] for x in report['edits']),
            'journal':str(journal),'vault_files_deleted':0}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--journal',type=Path)
    args=parser.parse_args()
    report=plan(args.vault)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if not args.apply: print(json.dumps({'planned_files':len(report['edits']),'errors':len(report['errors'])})); return
    if args.journal is None: parser.error('--apply requires --journal')
    print(json.dumps(apply(report,args.journal)))


if __name__=='__main__': main()
