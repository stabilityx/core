import boa
import pytest

from tests.mocks.deployers import MOCK_ERC20, MOCK_ORACLE
from tests.unitary.engine.conftest import POSITION_COLLATERAL, POSITION_DEBT
from tests.utils.constants import (
    COLLATERAL_DECIMALS,
    LIQUIDATION_BONUS,
    MAX_ORACLE_DELAY,
    MIN_COLLAT_RATIO,
    MIN_DEBT,
    ORACLE_DECIMALS,
    PRECISION,
    STABLE_DECIMALS,
)
from tests.utils.deployers import deploy_market
from tests.utils.engine_math import collateral_seized
from tests.utils.helpers import filter_logs, open_position, set_price

# 1 WETH backing 1000 mUSD at 1400 -> 140% CR: unhealthy but still solvent.
UNHEALTHY_PRICE = 1_400
# 1 WETH backing 1000 mUSD at 1000 -> 100% CR: collateral can't cover debt + bonus.
UNDERWATER_PRICE = 1_000


def _seized(debt: int, price: int) -> int:
    return collateral_seized(
        debt,
        price * 10**ORACLE_DECIMALS,
        COLLATERAL_DECIMALS,
        STABLE_DECIMALS,
        ORACLE_DECIMALS,
    )


# ================= Preconditions =================


def test_liquidate_healthy_position_reverts(engine, position, funded_liquidator):
    with boa.reverts(dev="engine: position is healthy"):
        engine.liquidate(position, sender=funded_liquidator)


def test_liquidate_at_exact_min_collat_ratio_reverts(engine, oracle, position, funded_liquidator):
    set_price(oracle, 1_500)
    assert engine.collat_ratio(position) == MIN_COLLAT_RATIO

    with boa.reverts(dev="engine: position is healthy"):
        engine.liquidate(position, sender=funded_liquidator)


def test_liquidate_position_without_debt_reverts(engine, borrower, funded_liquidator):
    with boa.reverts(dev="engine: position is healthy"):
        engine.liquidate(borrower, sender=funded_liquidator)


def test_liquidate_zero_amount_reverts(engine, oracle, position, funded_liquidator):
    set_price(oracle, UNHEALTHY_PRICE)

    with boa.reverts(dev="engine: amount must be greater than zero"):
        engine.liquidate(position, 0, sender=funded_liquidator)


def test_liquidate_with_stale_oracle_reverts(engine, oracle, position, funded_liquidator):
    set_price(oracle, UNHEALTHY_PRICE)
    boa.env.time_travel(seconds=MAX_ORACLE_DELAY + 1)

    with boa.reverts(dev="engine: stale oracle price"):
        engine.liquidate(position, sender=funded_liquidator)


def test_liquidate_without_stablecoin_reverts(engine, oracle, position, stranger):
    set_price(oracle, UNHEALTHY_PRICE)

    with boa.reverts("erc20: burn amount exceeds balance"):
        engine.liquidate(position, sender=stranger)


# ================= Full liquidation =================


def test_full_liquidation(engine, stablecoin, collateral_token, oracle, position, funded_liquidator):
    """Money Flow: liquidator stablecoin burned; collateral (+10% bonus) engine -> liquidator."""
    # ================= Setup =================
    set_price(oracle, UNHEALTHY_PRICE)
    expected_seized = _seized(POSITION_DEBT, UNHEALTHY_PRICE)

    # ================= Capture initial state =================
    liquidator_stable = stablecoin.balanceOf(funded_liquidator)
    engine_collateral = collateral_token.balanceOf(engine.address)
    total_supply = stablecoin.totalSupply()

    # ================= Execute =================
    engine.liquidate(position, sender=funded_liquidator)

    # ================= Verify state =================
    assert engine.address2minted(position) == 0
    assert engine.address2deposit(position) == POSITION_COLLATERAL - expected_seized
    assert engine.collat_ratio(position) == 2**256 - 1

    # ================= Verify money flows =================
    assert stablecoin.balanceOf(funded_liquidator) == liquidator_stable - POSITION_DEBT
    assert stablecoin.totalSupply() == total_supply - POSITION_DEBT
    assert collateral_token.balanceOf(funded_liquidator) == expected_seized
    assert collateral_token.balanceOf(engine.address) == engine_collateral - expected_seized

    # The bonus is worth ~10% of the debt covered.
    seized_value = expected_seized * UNHEALTHY_PRICE
    assert seized_value <= POSITION_DEBT * (PRECISION + LIQUIDATION_BONUS) // PRECISION
    assert seized_value > POSITION_DEBT * (PRECISION + LIQUIDATION_BONUS) // PRECISION - UNHEALTHY_PRICE

    # ================= Verify logs =================
    logs = filter_logs(engine, "Liquidate")
    assert len(logs) == 1
    assert logs[0].user == position
    assert logs[0].liquidator == funded_liquidator
    assert logs[0].debt_burned == POSITION_DEBT
    assert logs[0].collateral_seized == expected_seized


def test_liquidate_debt_to_cover_above_debt_is_clamped(engine, oracle, position, funded_liquidator):
    set_price(oracle, UNHEALTHY_PRICE)

    engine.liquidate(position, POSITION_DEBT * 3, sender=funded_liquidator)

    assert engine.address2minted(position) == 0
    assert filter_logs(engine, "Liquidate")[0].debt_burned == POSITION_DEBT


def test_borrower_keeps_surplus_collateral_after_liquidation(
    engine, collateral_token, oracle, position, funded_liquidator
):
    set_price(oracle, UNHEALTHY_PRICE)
    engine.liquidate(position, sender=funded_liquidator)
    surplus = engine.address2deposit(position)
    assert surplus > 0

    engine.withdraw(surplus, sender=position)

    assert collateral_token.balanceOf(position) == surplus


# ================= Underwater positions =================


def test_underwater_full_liquidation_seizes_all_collateral(
    engine, collateral_token, oracle, position, funded_liquidator
):
    set_price(oracle, UNDERWATER_PRICE)
    assert _seized(POSITION_DEBT, UNDERWATER_PRICE) > POSITION_COLLATERAL

    engine.liquidate(position, sender=funded_liquidator)

    assert engine.address2minted(position) == 0
    assert engine.address2deposit(position) == 0
    assert collateral_token.balanceOf(funded_liquidator) == POSITION_COLLATERAL
    assert filter_logs(engine, "Liquidate")[0].collateral_seized == POSITION_COLLATERAL


def test_underwater_partial_liquidation_reverts(engine, oracle, position, funded_liquidator):
    set_price(oracle, UNDERWATER_PRICE)

    with boa.reverts(dev="engine: must liquidate full debt when underwater"):
        engine.liquidate(position, POSITION_DEBT - 1, sender=funded_liquidator)


def test_liquidation_seizing_exactly_all_collateral(engine, collateral_token, oracle, position, funded_liquidator):
    """At 1100 the debt + bonus is worth exactly the whole deposit: the `>=` branch caps it."""
    set_price(oracle, 1_100)
    assert _seized(POSITION_DEBT, 1_100) == POSITION_COLLATERAL

    engine.liquidate(position, sender=funded_liquidator)

    assert engine.address2deposit(position) == 0
    assert engine.address2minted(position) == 0
    assert collateral_token.balanceOf(funded_liquidator) == POSITION_COLLATERAL


# ================= Partial liquidation =================


def test_partial_liquidation_restoring_health(
    engine, stablecoin, collateral_token, oracle, position, funded_liquidator
):
    set_price(oracle, UNHEALTHY_PRICE)
    debt_to_cover = 500 * 10**18
    expected_seized = _seized(debt_to_cover, UNHEALTHY_PRICE)
    liquidator_stable = stablecoin.balanceOf(funded_liquidator)

    engine.liquidate(position, debt_to_cover, sender=funded_liquidator)

    assert engine.address2minted(position) == POSITION_DEBT - debt_to_cover
    assert engine.address2deposit(position) == POSITION_COLLATERAL - expected_seized
    assert engine.collat_ratio(position) >= MIN_COLLAT_RATIO
    assert stablecoin.balanceOf(funded_liquidator) == liquidator_stable - debt_to_cover
    assert collateral_token.balanceOf(funded_liquidator) == expected_seized


def test_partial_liquidation_not_restoring_health_reverts(engine, oracle, position, funded_liquidator):
    set_price(oracle, UNHEALTHY_PRICE)

    with boa.reverts(dev="engine: partial liquidation must restore health"):
        engine.liquidate(position, 10 * 10**18, sender=funded_liquidator)


def test_partial_liquidation_leaving_dust_debt_reverts(engine, oracle, position, funded_liquidator):
    set_price(oracle, UNHEALTHY_PRICE)

    with boa.reverts(dev="engine: debt below minimum"):
        engine.liquidate(position, POSITION_DEBT - MIN_DEBT + 1, sender=funded_liquidator)


def test_partial_liquidation_leaving_exact_min_debt(engine, oracle, position, funded_liquidator):
    set_price(oracle, UNHEALTHY_PRICE)

    engine.liquidate(position, POSITION_DEBT - MIN_DEBT, sender=funded_liquidator)

    assert engine.address2minted(position) == MIN_DEBT


def test_self_liquidation(engine, stablecoin, collateral_token, oracle, position):
    """A borrower can liquidate themselves and still receive the bonus."""
    set_price(oracle, UNHEALTHY_PRICE)

    engine.liquidate(position, sender=position)

    assert engine.address2minted(position) == 0
    assert stablecoin.balanceOf(position) == 0
    assert collateral_token.balanceOf(position) == _seized(POSITION_DEBT, UNHEALTHY_PRICE)


def test_liquidate_transfer_returning_false_reverts(
    engine, collateral_token, oracle, position, funded_liquidator
):
    set_price(oracle, UNHEALTHY_PRICE)
    collateral_token.set_return_false(True)

    with boa.reverts(dev="engine: transfer failed"):
        engine.liquidate(position, sender=funded_liquidator)


# ================= Rounding =================


@pytest.fixture
def zero_decimal_market(factory, admin):
    """Indivisible collateral worth 1,000,000 mUSD per unit, quoted with 18 decimals."""
    token = MOCK_ERC20.deploy("Indivisible", "IND", 0)
    feed = MOCK_ORACLE.deploy(18, 1_000_000 * 10**18)
    stablecoin, engine = deploy_market(factory, admin, token, feed)
    return token, feed, stablecoin, engine


def test_liquidation_seizing_zero_collateral_reverts(zero_decimal_market, borrower, liquidator):
    token, feed, stablecoin, engine = zero_decimal_market

    # 1 unit (1,000,000) backing 600,000 -> 166%. Then the price drops to 800,000 -> 133%.
    open_position(engine, token, borrower, 1, 600_000 * 10**18)
    open_position(engine, token, liquidator, 10, 1_000 * 10**18)
    set_price(feed, 800_000)

    # Covering 1 mUSD would seize 1.375e-6 units, which rounds down to zero.
    with boa.reverts(dev="engine: collateral seized is zero"):
        engine.liquidate(borrower, 10**18, sender=liquidator)
