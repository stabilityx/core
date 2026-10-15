"""`# pragma nonreentrancy on` must block callbacks from a hostile collateral token."""

import boa

from tests.utils.helpers import deposit

AMOUNT = 5 * 10**18


def test_callback_succeeds_outside_engine_call(engine, collateral_token, borrower, stranger):
    """Control case: the hook itself is valid when no engine call is in progress."""
    collateral_token.set_callback(engine.address, engine.set_operator.prepare_calldata(stranger, True))
    collateral_token.mint(borrower, AMOUNT)

    collateral_token.transfer(stranger, AMOUNT, sender=borrower)

    assert engine.is_operator(collateral_token.address, stranger)


def test_reentrant_deposit_reverts(engine, collateral_token, borrower, stranger):
    collateral_token.set_callback(engine.address, engine.set_operator.prepare_calldata(stranger, True))
    collateral_token.mint(borrower, AMOUNT)
    collateral_token.approve(engine.address, AMOUNT, sender=borrower)

    with boa.reverts():
        engine.deposit(AMOUNT, sender=borrower)


def test_reentrant_withdraw_reverts(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, AMOUNT)
    collateral_token.set_callback(engine.address, engine.withdraw.prepare_calldata(1))

    with boa.reverts():
        engine.withdraw(AMOUNT, sender=borrower)

    assert engine.address2deposit(borrower) == AMOUNT
