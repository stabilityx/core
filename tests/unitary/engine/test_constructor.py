import boa
import pytest

from tests.mocks.deployers import MOCK_ERC20, MOCK_ORACLE
from tests.utils.constants import (
    COLLATERAL_DECIMALS,
    INITIAL_PRICE,
    LIQUIDATION_BONUS,
    MAX_ORACLE_DELAY,
    MAX_ORACLE_DELAY_LOWER_BOUND,
    MAX_ORACLE_DELAY_UPPER_BOUND,
    MIN_COLLAT_RATIO,
    MIN_COLLAT_RATIO_LOWER_BOUND,
    MIN_COLLAT_RATIO_UPPER_BOUND,
    MIN_DEBT,
    MIN_DEBT_LOWER_BOUND,
    MIN_DEBT_UPPER_BOUND,
    STABLE_DECIMALS,
    ZERO_ADDRESS,
)
from tests.utils.deployers import ENGINE_DEPLOYER, STABLE_DEPLOYER, deploy_engine_direct


# ================= Getters / immutables =================


def test_getters_return_constructor_args(engine, stablecoin, collateral_token, oracle):
    assert engine.collateral() == collateral_token.address
    assert engine.collateral_decimals() == COLLATERAL_DECIMALS
    assert engine.stablecoin() == stablecoin.address
    assert engine.stablecoin_decimals() == STABLE_DECIMALS
    assert engine.oracle() == oracle.address
    assert engine.MIN_COLLAT_RATIO() == MIN_COLLAT_RATIO
    assert engine.MAX_ORACLE_DELAY() == MAX_ORACLE_DELAY
    assert engine.MIN_DEBT() == MIN_DEBT
    assert engine.LIQUIDATION_BONUS() == LIQUIDATION_BONUS


def test_initial_state_is_empty(engine, borrower, operator):
    assert engine.address2deposit(borrower) == 0
    assert engine.address2minted(borrower) == 0
    assert not engine.is_operator(borrower, operator)


@pytest.mark.parametrize("collateral_decimals", [0, 6, 8, 18])
def test_reads_collateral_decimals(collateral_decimals, oracle):
    token = MOCK_ERC20.deploy("Token", "TKN", collateral_decimals)
    engine = deploy_engine_direct(token, oracle)
    assert engine.collateral_decimals() == collateral_decimals


@pytest.mark.parametrize("stable_decimals", [0, 6, 18])
def test_reads_stablecoin_decimals(stable_decimals, collateral_token, oracle):
    engine = deploy_engine_direct(collateral_token, oracle, stable_decimals=stable_decimals)
    assert engine.stablecoin_decimals() == stable_decimals


# ================= Zero-address checks =================


def test_zero_collateral_reverts(stablecoin, oracle):
    with boa.reverts(dev="engine: collateral is the zero address"):
        ENGINE_DEPLOYER.deploy(ZERO_ADDRESS, stablecoin.address, oracle.address, MIN_COLLAT_RATIO, MAX_ORACLE_DELAY, MIN_DEBT)


def test_zero_stablecoin_reverts(collateral_token, oracle):
    with boa.reverts(dev="engine: stablecoin is the zero address"):
        deploy_engine_direct(collateral_token, oracle, stablecoin_address=ZERO_ADDRESS)


def test_zero_oracle_reverts(collateral_token, stablecoin):
    with boa.reverts(dev="engine: oracle is the zero address"):
        ENGINE_DEPLOYER.deploy(collateral_token.address, stablecoin.address, ZERO_ADDRESS, MIN_COLLAT_RATIO, MAX_ORACLE_DELAY, MIN_DEBT)


# ================= Parameter bounds =================


@pytest.mark.parametrize(
    "min_collat_ratio",
    [MIN_COLLAT_RATIO_LOWER_BOUND, MIN_COLLAT_RATIO, MIN_COLLAT_RATIO_UPPER_BOUND],
)
def test_min_collat_ratio_within_bounds(min_collat_ratio, collateral_token, oracle):
    engine = deploy_engine_direct(collateral_token, oracle, min_collat_ratio=min_collat_ratio)
    assert engine.MIN_COLLAT_RATIO() == min_collat_ratio


@pytest.mark.parametrize(
    "min_collat_ratio",
    [0, 10**18, MIN_COLLAT_RATIO_LOWER_BOUND - 1, MIN_COLLAT_RATIO_UPPER_BOUND + 1],
)
def test_min_collat_ratio_out_of_bounds_reverts(min_collat_ratio, collateral_token, oracle):
    with boa.reverts(dev="engine: invalid min collateral ratio"):
        deploy_engine_direct(collateral_token, oracle, min_collat_ratio=min_collat_ratio)


@pytest.mark.parametrize(
    "max_oracle_delay",
    [MAX_ORACLE_DELAY_LOWER_BOUND, MAX_ORACLE_DELAY, MAX_ORACLE_DELAY_UPPER_BOUND],
)
def test_max_oracle_delay_within_bounds(max_oracle_delay, collateral_token, oracle):
    engine = deploy_engine_direct(collateral_token, oracle, max_oracle_delay=max_oracle_delay)
    assert engine.MAX_ORACLE_DELAY() == max_oracle_delay


@pytest.mark.parametrize(
    "max_oracle_delay",
    [0, MAX_ORACLE_DELAY_LOWER_BOUND - 1, MAX_ORACLE_DELAY_UPPER_BOUND + 1],
)
def test_max_oracle_delay_out_of_bounds_reverts(max_oracle_delay, collateral_token, oracle):
    with boa.reverts(dev="engine: invalid max oracle delay"):
        deploy_engine_direct(collateral_token, oracle, max_oracle_delay=max_oracle_delay)


@pytest.mark.parametrize("min_debt", [MIN_DEBT_LOWER_BOUND, MIN_DEBT, MIN_DEBT_UPPER_BOUND])
def test_min_debt_within_bounds(min_debt, collateral_token, oracle):
    engine = deploy_engine_direct(collateral_token, oracle, min_debt=min_debt)
    assert engine.MIN_DEBT() == min_debt


@pytest.mark.parametrize("min_debt", [0, MIN_DEBT_LOWER_BOUND - 1, MIN_DEBT_UPPER_BOUND + 1])
def test_min_debt_out_of_bounds_reverts(min_debt, collateral_token, oracle):
    with boa.reverts(dev="engine: invalid min debt"):
        deploy_engine_direct(collateral_token, oracle, min_debt=min_debt)


# ================= Decimals checks =================


def test_collateral_decimals_above_18_reverts(oracle):
    token = MOCK_ERC20.deploy("Token", "TKN", 19)
    with boa.reverts(dev="engine: collateral decimals exceed 18"):
        deploy_engine_direct(token, oracle)


def test_stablecoin_decimals_above_18_reverts(collateral_token, oracle):
    with boa.reverts(dev="engine: stablecoin decimals exceed 18"):
        deploy_engine_direct(collateral_token, oracle, stable_decimals=19)


def test_oracle_decimals_above_18_reverts(collateral_token):
    oracle = MOCK_ORACLE.deploy(19, INITIAL_PRICE * 10**19)
    with boa.reverts(dev="engine: oracle decimals exceed 18"):
        deploy_engine_direct(collateral_token, oracle)


# ================= Oracle sanity check at deploy =================


def test_oracle_never_updated_reverts(collateral_token, oracle):
    oracle.set_timestamp(0)
    with boa.reverts(dev="engine: oracle never updated"):
        deploy_engine_direct(collateral_token, oracle)


def test_stale_oracle_reverts(collateral_token, oracle):
    oracle.set_timestamp(boa.env.timestamp - MAX_ORACLE_DELAY - 1)
    with boa.reverts(dev="engine: stale oracle price"):
        deploy_engine_direct(collateral_token, oracle)


def test_zero_oracle_price_reverts(collateral_token, oracle):
    oracle.set_answer(0)
    with boa.reverts(dev="engine: invalid oracle price"):
        deploy_engine_direct(collateral_token, oracle)


def test_engine_without_stablecoin_ownership_cannot_mint(collateral_token, oracle, borrower):
    """The engine does not check stablecoin ownership; wiring it is the deployer's job."""
    stablecoin = STABLE_DEPLOYER.deploy("Unowned", "UNO", STABLE_DECIMALS)
    engine = deploy_engine_direct(collateral_token, oracle, stablecoin_address=stablecoin.address)
    assert stablecoin.owner() != engine.address

    collateral_token.mint(borrower, 10**18)
    collateral_token.approve(engine.address, 10**18, sender=borrower)
    engine.deposit(10**18, sender=borrower)

    with boa.reverts("ownable: caller is not the owner"):
        engine.mint(MIN_DEBT, sender=borrower)
