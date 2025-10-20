"""Top level package for ApexInvest Advisor.

This package contains shared code used across multiple services
(backend, data ingestion, etc.).  Importing this package ensures that
Python treats the directory as a package and allows absolute imports
such as ``from apexinvest_advisor.config import CONFIG``.
"""

__all__ = ["config"]