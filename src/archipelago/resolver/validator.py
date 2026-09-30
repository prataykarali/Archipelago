"""Re-export validator from archipelago.resolver.validator."""
from archipelago.resolver.validator import check_url_async, check_url_sync, is_safe_url

__all__ = ["check_url_sync", "check_url_async", "is_safe_url"]
