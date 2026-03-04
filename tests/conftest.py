"""
Pytest Configuration & Fixtures
=================================
Shared fixtures for the Match Maker test suite.
"""

import os
import sys
import tempfile

import pytest

# Ensure project root is on sys.path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure import (
    EnhancedEventDispatcher,
    InMemoryCache,
    InProcessLock,
    Paginator,
)
from security import (
    CSRFProtection,
    InputValidator,
    JWTProvider,
    PasswordPolicy,
    RateLimiter,
)
from tournament_calculators import StandardPointsCalculator
from tournament_calculators_ext import (
    BuchholzCalculator,
    ByeCalculator,
    DirectEncounterCalculator,
    GlickoRatingCalculator,
    SonnebornBergerCalculator,
)
from tournament_core import (
    MatchmakingStrategyRegistry,
    PointsCalculatorRegistry,
)
from tournament_repository import SQLiteTournamentRepository
from tournament_service import TournamentService
from tournament_strategies import (
    FreeForAllStrategy,
    RoundRobinStrategy,
    SingleEliminationStrategy,
    SwissStrategy,
)
from tournament_strategies_ext import (
    ColorBalancedSwissStrategy,
    DoubleEliminationStrategy,
)

# ──────────────────────────────────────────────────────────────────────
#  DB Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db_path():
    """Create a temporary SQLite database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def repository(tmp_db_path):
    """Provide a clean SQLiteTournamentRepository."""
    return SQLiteTournamentRepository(tmp_db_path)


# ──────────────────────────────────────────────────────────────────────
#  Registry Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def strategy_registry(repository):
    """Strategy registry with all built-in + extended strategies."""
    reg = MatchmakingStrategyRegistry()
    for s in [
        RoundRobinStrategy(),
        SingleEliminationStrategy(),
        SwissStrategy(),
        FreeForAllStrategy(),
        DoubleEliminationStrategy(),
        ColorBalancedSwissStrategy(),
    ]:
        reg.register(s)
    return reg


@pytest.fixture
def calculator_registry(repository):
    """Calculator registry with all built-in + extended calculators."""
    reg = PointsCalculatorRegistry()
    for c in [
        StandardPointsCalculator(),
        BuchholzCalculator(repository),
        SonnebornBergerCalculator(repository),
        DirectEncounterCalculator(),
        ByeCalculator(),
        GlickoRatingCalculator(),
    ]:
        reg.register(c)
    return reg


# ──────────────────────────────────────────────────────────────────────
#  Service Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def service(repository, strategy_registry, calculator_registry):
    """Fully initialised TournamentService."""
    return TournamentService(repository, strategy_registry, calculator_registry)


# ──────────────────────────────────────────────────────────────────────
#  Infrastructure Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def paginator():
    return Paginator()


@pytest.fixture
def lock():
    return InProcessLock()


@pytest.fixture
def cache():
    return InMemoryCache()


@pytest.fixture
def event_dispatcher():
    return EnhancedEventDispatcher()


# ──────────────────────────────────────────────────────────────────────
#  Security Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def password_policy():
    return PasswordPolicy(min_length=8)


@pytest.fixture
def input_validator():
    return InputValidator()


@pytest.fixture
def rate_limiter():
    return RateLimiter(max_attempts=3, lockout_seconds=5)


@pytest.fixture
def jwt_provider():
    return JWTProvider(secret="test-secret")


@pytest.fixture
def csrf_protection():
    return CSRFProtection(secret_key="test-csrf-key")
