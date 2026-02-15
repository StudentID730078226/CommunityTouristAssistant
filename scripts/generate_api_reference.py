"""Generate a plain reStructuredText API reference from docstrings.

This is used to render the API reference reliably in rinoh PDF output.
"""

from __future__ import annotations

import importlib
import inspect
import textwrap
from pathlib import Path
import os
import sys

import django


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "sphinx" / "source" / "api_generated.rst"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "community_tourism.settings")
django.setup()

MODULE_GROUPS = {
    "Accounts": [
        "accounts.models",
        "accounts.views",
        "accounts.signals",
    ],
    "Places": [
        "places.models",
        "places.forms",
        "places.views",
        "places.utils",
    ],
    "Reviews": [
        "reviews.models",
        "reviews.forms",
        "reviews.views",
        "reviews.spam",
        "reviews.moderation",
    ],
}


def _heading(title: str, level_char: str) -> str:
    return f"{title}\n{level_char * len(title)}\n\n"


def _clean_docstring(doc: str | None) -> str:
    if not doc:
        return "No documentation available.\n"
    return textwrap.dedent(doc).strip() + "\n"


def _iter_class_members(cls):
    for name, member in cls.__dict__.items():
        if name.startswith("_") and name not in {"__str__", "__init__"}:
            continue
        if isinstance(member, property) and member.fget:
            yield name, member.fget, "property"
        elif inspect.isfunction(member):
            yield name, member, "method"


def _write_class_doc(out, cls):
    out.write(_heading(cls.__name__, "~"))
    out.write(_clean_docstring(inspect.getdoc(cls)))
    out.write("\n")

    for name, member, member_type in _iter_class_members(cls):
        title = f"{cls.__name__}.{name}"
        out.write(_heading(title, "\""))
        out.write(_clean_docstring(inspect.getdoc(member)))
        out.write("\n")


def _write_function_doc(out, func, module_name: str):
    title = f"{module_name}.{func.__name__}"
    out.write(_heading(title, "~"))
    out.write(_clean_docstring(inspect.getdoc(func)))
    out.write("\n")


def _write_module_section(out, module_name: str):
    module = importlib.import_module(module_name)
    out.write(_heading(module_name, "^"))
    out.write(_clean_docstring(inspect.getdoc(module)))
    out.write("\n")

    for _name, cls in inspect.getmembers(module, inspect.isclass):
        if cls.__module__ != module.__name__:
            continue
        _write_class_doc(out, cls)

    for _name, func in inspect.getmembers(module, inspect.isfunction):
        if func.__module__ != module.__name__:
            continue
        if func.__name__.startswith("_"):
            continue
        _write_function_doc(out, func, module.__name__)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as out:
        out.write(_heading("API Reference (Generated)", "="))
        out.write("This section is generated directly from docstrings.\n\n")

        for group, modules in MODULE_GROUPS.items():
            out.write(_heading(group, "-"))
            for module_name in modules:
                _write_module_section(out, module_name)


if __name__ == "__main__":
    main()
