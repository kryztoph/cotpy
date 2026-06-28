"""COT Data Analysis Tool package."""

from importlib import import_module

__all__ = [
    "Config",
    "COTFetcher",
    "COTParser",
    "COTAnalyzer",
    "SignalGenerator",
    "COTVisualizer",
]

_MODULE_MAP = {
    "Config": "config",
    "COTFetcher": "fetcher",
    "COTParser": "parser",
    "COTAnalyzer": "analyzer",
    "SignalGenerator": "signals",
    "COTVisualizer": "visualizer",
}


def __getattr__(name: str):
    """Lazily load top-level exports so optional deps stay optional."""
    module_name = _MODULE_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(f".{module_name}", __name__)
    return getattr(module, name)
