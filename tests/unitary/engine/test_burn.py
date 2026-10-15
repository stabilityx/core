import boa

from tests.unitary.engine.conftest import POSITION_DEBT
from tests.utils.constants import MAX_ORACLE_DELAY, MIN_DEBT, ZERO_ADDRESS
from tests.utils.helpers import filter_logs


def test_burn_reduces_debt_and_balance(engine, stablecoin, position):
    """Money Flow: stablecoin burned from borrower, debt reduced on borrower."""
    amount = 400 * 10**18

    # ================= Execute =================
    engine.burn(amount, sender=position)

    # ================= Verify state, logs, money flows =================
    assert engine.address2minted(position) == POSITION_DEBT - amount
    assert stablecoin.balanceOf(position) == POSITION_DEBT - amount
    assert stablecoin.totalSupply() == POSITION_DEBT - amount

    logs = filter_logs(engine, "Burn")
    assert len(logs) == 1
    assert logs[0].caller == position
    assert logs[0].user == position
    assert logs[0].amount == amount


def test_burn_full_debt(engine, stablecoin, position):
    """Repaying to zero is allowed; the debt floor only applies to non-zero debt."""
    engine.burn(POSITION_DEBT, sender=position)

    assert engine.address2minted(position) == 0
    assert stablecoin.balanceOf(position) == 0
    assert engine.collat_ratio(position) == 2**256 - 1


def test_burn_down_to_exact_min_debt(engine, position):
    engine.burn(POSITION_DEBT - MIN_DEBT, sender=position)

    assert engine.address2minted(position) == MIN_DEBT


def test_burn_leaving_dust_debt_reverts(engine, position):
    with boa.reverts(dev="engine: debt below minimum"):
        engine.burn(POSITION_DEBT - MIN_DEBT + 1, sender=position)


def test_burn_more_than_debt_reverts(engine, stablecoin, position):
    # Give the borrower extra stablecoin so the revert comes from the debt underflow.
    stablecoin.mint(position, 1, sender=engine.address)

    with boa.reverts():
        engine.burn(POSITION_DEBT + 1, sender=position)


def test_burn_on_behalf_of_repays_user_with_caller_funds(engine, stablecoin, position, stranger):
    """Anyone may repay anyone's debt; the caller's tokens are burned."""
    amount = 300 * 10**18
    stablecoin.transfer(stranger, amount, sender=position)

    engine.burn(amount, position, sender=stranger)

    assert engine.address2minted(position) == POSITION_DEBT - amount
    assert stablecoin.balanceOf(stranger) == 0
    assert stablecoin.balanceOf(position) == POSITION_DEBT - amount

    logs = filter_logs(engine, "Burn")
    assert logs[0].caller == stranger
    assert logs[0].user == position


def test_burn_without_balance_reverts(engine, position, stranger):
    with boa.reverts("erc20: burn amount exceeds balance"):
        engine.burn(MIN_DEBT, position, sender=stranger)


def test_burn_without_debt_reverts(engine, stablecoin, position, stranger):
    stablecoin.transfer(stranger, MIN_DEBT, sender=position)

    with boa.reverts():
        engine.burn(MIN_DEBT, sender=stranger)


def test_burn_zero_amount_reverts(engine, position):
    with boa.reverts(dev="engine: amount must be greater than zero"):
        engine.burn(0, sender=position)


def test_burn_on_behalf_of_zero_address_reverts(engine, position):
    with boa.reverts(dev="engine: user is the zero address"):
        engine.burn(MIN_DEBT, ZERO_ADDRESS, sender=position)


def test_burn_ignores_stale_oracle(engine, oracle, position):
    """Repayment must always be possible, even when the price feed is down."""
    boa.env.time_travel(seconds=MAX_ORACLE_DELAY + 1)
    oracle.set_answer(0)

    engine.burn(POSITION_DEBT, sender=position)

    assert engine.address2minted(position) == 0
