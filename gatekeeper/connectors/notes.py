"""Example connector: a folder of Markdown notes (works with Obsidian vaults, plain folders...).

Sensitivity comes from (1) the subfolder name as a source tag, (2) `tags:` in front matter,
and (3) the content classifier. Search returns matching note titles plus a short excerpt
rather than whole documents.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..classifier import classify_text
from ..models import CATEGORIES, Item
from .base import Connector, Context, Operation

FOLDER_TAGS = {"finance": "financial", "money": "financial", "health": "health",
               "medical": "health", "work": "work", "people": "people", "private": "private_notes"}
EXCERPT_CHARS = 160


@dataclass(frozen=True)
class Note:
    id: str
    title: str
    body: str
    tags: frozenset[str]


def _parse(path: Path, root: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    tags: set[str] = set()
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if fm:
        text = text[fm.end():]
        m = re.search(r"^tags:\s*\[(.*?)\]", fm.group(1), re.MULTILINE)
        if m:
            tags |= {t.strip().strip("'\"") for t in m.group(1).split(",")} & CATEGORIES
    rel = path.relative_to(root)
    for part in rel.parts[:-1]:
        if part.lower() in FOLDER_TAGS:
            tags.add(FOLDER_TAGS[part.lower()])
    h1 = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    title = h1.group(1).strip() if h1 else path.stem.replace("-", " ")
    return Note(id=f"note:{rel.with_suffix('').as_posix()}", title=title, body=text.strip(), tags=frozenset(tags))


class NotesConnector(Connector):
    name = "notes"
    description = "The user's personal notes and documents (Markdown files)."

    def __init__(self, root: Path):
        self.root = root

    def _notes(self) -> list[Note]:
        return [_parse(p, self.root) for p in sorted(self.root.rglob("*.md"))]

    def operations(self) -> list[Operation]:
        return [
            Operation("count", "How many notes match a topic (or in total). Reveals no content.",
                      self.count, {"query": "optional keyword"}, exposure=1),
            Operation("search", f"Titles of notes matching a keyword, with a short (~{EXCERPT_CHARS} char) "
                      "excerpt around the match.", self.search, {"query": "keyword to search for"}, exposure=2),
            Operation("read", "Full text of one note by its id (from search).", self.read,
                      {"id": "note id returned by search"}, exposure=3),
        ]

    @staticmethod
    def _cats(note: Note, text: str) -> set[str]:
        return set(note.tags) | classify_text(note.title) | classify_text(text) or {"general"}

    def _match(self, query) -> list[Note]:
        q = (query or "").lower()
        return [n for n in self._notes() if q in n.title.lower() or q in n.body.lower()]

    def count(self, ctx: Context, query=None) -> list[Item]:
        return [Item(id="notes:count", data={"query": query, "count": len(self._match(query))},
                     categories={"general"})]

    def search(self, ctx: Context, query: str = "") -> list[Item]:
        if not query:
            raise ValueError("query is required")
        items = []
        for n in self._match(query):
            i = n.body.lower().find(query.lower())
            start = max(0, i - EXCERPT_CHARS // 2) if i >= 0 else 0
            excerpt = n.body[start:start + EXCERPT_CHARS].replace("\n", " ").strip()
            items.append(Item(id=n.id, data={"id": n.id, "title": n.title, "excerpt": excerpt},
                              categories=self._cats(n, excerpt)))
        return items

    def read(self, ctx: Context, id: str = "") -> list[Item]:
        note = next((n for n in self._notes() if n.id == id), None)
        if not note:
            raise ValueError(f"No note with id {id!r}")
        return [Item(id=note.id, data={"id": note.id, "title": note.title, "body": note.body},
                     categories=self._cats(note, note.body) | {"private_notes"})]
