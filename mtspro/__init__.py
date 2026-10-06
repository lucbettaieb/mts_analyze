"""mtspro: analyze and convert Master Tracks Pro (Passport Designs) song files."""
from .parser import MTSFormatError, parse, parse_file
from .writer import serialize

__all__ = ["parse", "parse_file", "serialize", "MTSFormatError"]
__version__ = "1.0.0"
