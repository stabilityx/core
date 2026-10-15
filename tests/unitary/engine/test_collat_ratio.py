import boa
import pytest

from tests.unitary.engine.conftest import POSITION_COLLATERAL, POSITION_DEBT
from tests.utils.constants import (
    COLLATERAL_DECIMALS,
    MAX_ORACLE_DELAY,
    MAX_UINT256,
    ORACLE_DECIMALS,
    STABLE_DECIMALS,
)
from tests.utils.engine_math import collat_ratio
from tests.utils.helpers import deposit, set_price


def test_collat_ratio_without_position(engine, borrower):
    assert engine.collat_ratio(borrower) == MAX_UINT256


def test_collat_ratio_with_only_collateral(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, POSITION_COLLATERAL)

    assert engine.collat_ratio(borrower) == MAX_UINT256


def test_collat_ratio_without_debt_ignores_broken_oracle(engine, collateral_token, oracle, borrower):
    deposit(engine, collateral_token, borrower, POSITION_COLLATERAL)
    oracle.set_timestamp(0)
    oracle.set_answer(0)

    assert engine.collat_ratio(borrower) == MAX_UINT256


def test_collat_ratio_with_debt(engine, position):
    assert engine.collat_ratio(position) == 2 * 10**18


@pytest.mark.parametrize("price", [1, 750, 1_400, 1_500, 2_000, 3_333, 100_000])
def test_collat_ratio_tracks_price(engine, oracle, position, price):
    set_price(oracle, price)

    expected = collat_ratio(
        POSITION_COLLATERAL,
        POSITION_DEBT,
        price * 10**ORACLE_DECIMALS,
        COLLATERAL_DECIMALS,
        STABLE_DECIMALS,
        ORACLE_DECIMALS,
    )
    assert engine.collat_ratio(position) == expected
    assert expected == price * 10**18 // 1_000


def test_collat_ratio_with_debt_and_stale_oracle_reverts(engine, position):
    boa.env.time_travel(seconds=MAX_ORACLE_DELAY + 1)

    with boa.reverts(dev="engine: stale oracle price"):
        engine.collat_ratio(position)
