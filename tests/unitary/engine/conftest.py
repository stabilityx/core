import pytest

from tests.utils.helpers import open_position

# Default position used across engine tests: 1 WETH @ 2000 backing 1000 mUSD -> 200% CR.
POSITION_COLLATERAL = 10**18
POSITION_DEBT = 1_000 * 10**18


@pytest.fixture
def position(engine, collateral_token, borrower):
    """`borrower` holds a healthy 200% CR position."""
    open_position(engine, collateral_token, borrower, POSITION_COLLATERAL, POSITION_DEBT)
    return borrower


@pytest.fixture
def funded_liquidator(engine, collateral_token, liquidator):
    """`liquidator` holds 5000 mUSD, backed by an over-collateralised position of their own."""
    open_position(engine, collateral_token, liquidator, 100 * 10**18, 5_000 * 10**18)
    return liquidator
