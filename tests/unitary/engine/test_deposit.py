import boa

from tests.utils.constants import MAX_ORACLE_DELAY, MAX_UINT256, ZERO_ADDRESS
from tests.utils.helpers import deposit, filter_logs

AMOUNT = 5 * 10**18


def test_deposit_credits_caller(engine, collateral_token, borrower):
    """Money Flow: collateral borrower -> engine."""
    # ================= Setup =================
    collateral_token.mint(borrower, AMOUNT)
    collateral_token.approve(engine.address, AMOUNT, sender=borrower)

    # ================= Execute =================
    engine.deposit(AMOUNT, sender=borrower)

    # ================= Verify state, logs, money flows =================
    assert engine.address2deposit(borrower) == AMOUNT
    assert engine.address2minted(borrower) == 0
    assert collateral_token.balanceOf(borrower) == 0
    assert collateral_token.balanceOf(engine.address) == AMOUNT

    logs = filter_logs(engine, "Deposit")
    assert len(logs) == 1
    assert logs[0].caller == borrower
    assert logs[0].user == borrower
    assert logs[0].amount == AMOUNT


def test_deposit_on_behalf_of_credits_user(engine, collateral_token, borrower, stranger):
    """Money Flow: collateral stranger -> engine, credited to borrower."""
    deposit(engine, collateral_token, stranger, AMOUNT, on_behalf_of=borrower)

    assert engine.address2deposit(borrower) == AMOUNT
    assert engine.address2deposit(stranger) == 0
    assert collateral_token.balanceOf(engine.address) == AMOUNT

    logs = filter_logs(engine, "Deposit")
    assert logs[0].caller == stranger
    assert logs[0].user == borrower


def test_deposit_accumulates(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, AMOUNT)
    deposit(engine, collateral_token, borrower, AMOUNT)

    assert engine.address2deposit(borrower) == 2 * AMOUNT
    assert collateral_token.balanceOf(engine.address) == 2 * AMOUNT


def test_deposit_does_not_need_oracle(engine, collateral_token, oracle, borrower):
    """Deposits never consult the oracle, so they keep working when it is stale."""
    boa.env.time_travel(seconds=MAX_ORACLE_DELAY + 1)
    oracle.set_timestamp(0)

    deposit(engine, collateral_token, borrower, AMOUNT)

    assert engine.address2deposit(borrower) == AMOUNT


def test_deposit_zero_amount_reverts(engine, borrower):
    with boa.reverts(dev="engine: amount must be greater than zero"):
        engine.deposit(0, sender=borrower)


def test_deposit_on_behalf_of_zero_address_reverts(engine, collateral_token, borrower):
    collateral_token.mint(borrower, AMOUNT)
    collateral_token.approve(engine.address, AMOUNT, sender=borrower)

    with boa.reverts(dev="engine: user is the zero address"):
        engine.deposit(AMOUNT, ZERO_ADDRESS, sender=borrower)


def test_deposit_without_allowance_reverts(engine, collateral_token, borrower):
    collateral_token.mint(borrower, AMOUNT)

    with boa.reverts():
        engine.deposit(AMOUNT, sender=borrower)


def test_deposit_without_balance_reverts(engine, collateral_token, borrower):
    collateral_token.approve(engine.address, MAX_UINT256, sender=borrower)

    with boa.reverts():
        engine.deposit(AMOUNT, sender=borrower)


def test_deposit_transfer_returning_false_reverts(engine, collateral_token, borrower):
    collateral_token.mint(borrower, AMOUNT)
    collateral_token.approve(engine.address, AMOUNT, sender=borrower)
    collateral_token.set_return_false(True)

    with boa.reverts(dev="engine: transfer failed"):
        engine.deposit(AMOUNT, sender=borrower)
