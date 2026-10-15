import boa

from tests.unitary.engine.conftest import POSITION_COLLATERAL, POSITION_DEBT
from tests.utils.constants import MAX_ORACLE_DELAY, MIN_COLLAT_RATIO, ZERO_ADDRESS
from tests.utils.helpers import deposit, filter_logs, set_price

AMOUNT = 5 * 10**18


def test_withdraw_without_debt(engine, collateral_token, borrower):
    """Money Flow: collateral engine -> borrower."""
    # ================= Setup =================
    deposit(engine, collateral_token, borrower, AMOUNT)

    # ================= Execute =================
    engine.withdraw(AMOUNT, sender=borrower)

    # ================= Verify state, logs, money flows =================
    assert engine.address2deposit(borrower) == 0
    assert collateral_token.balanceOf(borrower) == AMOUNT
    assert collateral_token.balanceOf(engine.address) == 0

    logs = filter_logs(engine, "Withdraw")
    assert len(logs) == 1
    assert logs[0].caller == borrower
    assert logs[0].user == borrower
    assert logs[0].receiver == borrower
    assert logs[0].amount == AMOUNT


def test_withdraw_to_receiver(engine, collateral_token, borrower, receiver):
    deposit(engine, collateral_token, borrower, AMOUNT)

    engine.withdraw(AMOUNT, borrower, receiver, sender=borrower)

    assert collateral_token.balanceOf(receiver) == AMOUNT
    assert collateral_token.balanceOf(borrower) == 0
    assert filter_logs(engine, "Withdraw")[0].receiver == receiver


def test_withdraw_partial(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, AMOUNT)

    engine.withdraw(AMOUNT // 4, sender=borrower)

    assert engine.address2deposit(borrower) == AMOUNT - AMOUNT // 4
    assert collateral_token.balanceOf(borrower) == AMOUNT // 4


def test_withdraw_with_debt_keeps_position_healthy(engine, collateral_token, position):
    # 1 WETH @ 2000 / 1000 debt = 200%. Withdrawing 0.25 WETH -> 150% (exactly the minimum).
    engine.withdraw(POSITION_COLLATERAL // 4, sender=position)

    assert engine.collat_ratio(position) == MIN_COLLAT_RATIO
    assert engine.address2deposit(position) == POSITION_COLLATERAL * 3 // 4


def test_withdraw_below_min_collat_ratio_reverts(engine, position):
    with boa.reverts(dev="engine: below min collateral ratio"):
        engine.withdraw(POSITION_COLLATERAL // 4 + 1, sender=position)


def test_withdraw_all_with_debt_reverts(engine, position):
    with boa.reverts(dev="engine: below min collateral ratio"):
        engine.withdraw(POSITION_COLLATERAL, sender=position)


def test_withdraw_after_full_repay(engine, collateral_token, position):
    engine.burn(POSITION_DEBT, sender=position)

    engine.withdraw(POSITION_COLLATERAL, sender=position)

    assert engine.address2deposit(position) == 0
    assert collateral_token.balanceOf(position) == POSITION_COLLATERAL


def test_withdraw_more_than_deposited_reverts(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, AMOUNT)

    with boa.reverts():
        engine.withdraw(AMOUNT + 1, sender=borrower)


def test_withdraw_zero_amount_reverts(engine, borrower):
    with boa.reverts(dev="engine: amount must be greater than zero"):
        engine.withdraw(0, sender=borrower)


def test_withdraw_to_zero_address_reverts(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, AMOUNT)

    with boa.reverts(dev="engine: receiver is the zero address"):
        engine.withdraw(AMOUNT, borrower, ZERO_ADDRESS, sender=borrower)


def test_withdraw_unauthorized_reverts(engine, collateral_token, borrower, stranger):
    deposit(engine, collateral_token, borrower, AMOUNT)

    with boa.reverts(dev="engine: caller is not authorized"):
        engine.withdraw(AMOUNT, borrower, stranger, sender=stranger)


def test_withdraw_transfer_returning_false_reverts(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, AMOUNT)
    collateral_token.set_return_false(True)

    with boa.reverts(dev="engine: transfer failed"):
        engine.withdraw(AMOUNT, sender=borrower)


# ================= Oracle independence for debt-free positions =================


def test_withdraw_without_debt_ignores_stale_oracle(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, AMOUNT)
    boa.env.time_travel(seconds=MAX_ORACLE_DELAY + 1)

    engine.withdraw(AMOUNT, sender=borrower)

    assert collateral_token.balanceOf(borrower) == AMOUNT


def test_withdraw_without_debt_ignores_broken_oracle(engine, collateral_token, oracle, borrower):
    deposit(engine, collateral_token, borrower, AMOUNT)
    oracle.set_answer(0)
    oracle.set_timestamp(0)

    engine.withdraw(AMOUNT, sender=borrower)

    assert collateral_token.balanceOf(borrower) == AMOUNT


def test_withdraw_with_debt_and_stale_oracle_reverts(engine, position):
    boa.env.time_travel(seconds=MAX_ORACLE_DELAY + 1)

    with boa.reverts(dev="engine: stale oracle price"):
        engine.withdraw(1, sender=position)


def test_withdraw_with_debt_after_price_drop_reverts(engine, oracle, position):
    # 1 WETH @ 1500 / 1000 debt = 150%: any withdrawal breaks the ratio.
    set_price(oracle, 1_500)

    with boa.reverts(dev="engine: below min collateral ratio"):
        engine.withdraw(1, sender=position)
