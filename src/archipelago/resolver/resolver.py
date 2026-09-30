"""Re-export resolver from archipelago.resolver.resolver."""
from archipelago.resolver.resolver import LinkResolver, resolve_book, resolve_url

__all__ = ["LinkResolver", "resolve_book", "resolve_url"]
