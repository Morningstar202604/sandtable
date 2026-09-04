"""结构化日志模块，替代裸 print / 吞掉异常的 except Exception。"""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger("wargame")

if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def setup(level: str = "INFO") -> None:
    """配置日志级别。"""
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))


def debug(msg: str, **kwargs: Any) -> None:
    logger.debug("%s | %s", msg, kwargs)


def info(msg: str, **kwargs: Any) -> None:
    logger.info("%s | %s", msg, kwargs)


def warning(msg: str, **kwargs: Any) -> None:
    logger.warning("%s | %s", msg, kwargs)


def error(msg: str, **kwargs: Any) -> None:
    logger.error("%s | %s", msg, kwargs)


def exception(msg: str, exc: BaseException | None = None, **kwargs: Any) -> None:
    extra = {**kwargs}
    if exc:
        extra["error"] = repr(exc)
    logger.exception("%s | %s", msg, extra)
