# -*- coding: utf-8 -*-
"""Shared path helpers.

所有脚本都用这里推导路径，避免写死个人机器上的绝对路径。
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

WORKSPACE = REPO_ROOT / "workspace"
SOURCE_DIR = WORKSPACE / "source"
INTERIM_DIR = WORKSPACE / "interim"
OUTPUT_DIR = WORKSPACE / "output"

DEFAULT_BOOK = "alpine-skills-summer"


def book_dir(name: str = DEFAULT_BOOK) -> Path:
    return REPO_ROOT / "books" / name


def glossary_dir(name: str = DEFAULT_BOOK) -> Path:
    return book_dir(name) / "glossary"


def parse_dir(name: str = DEFAULT_BOOK) -> Path:
    """MinerU 解析产物目录（markdown.md + images/）。"""
    return INTERIM_DIR / f"parse-{name}"


def ensure_dirs() -> None:
    for d in (SOURCE_DIR, INTERIM_DIR, OUTPUT_DIR):
        d.mkdir(parents=True, exist_ok=True)
