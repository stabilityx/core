import boa

from tests.utils.constants import MIN_DEBT, ZERO_ADDRESS
from tests.utils.helpers import deposit, filter_logs

COLLATERAL = 3 * 10**18


def test_set_operator_approves(engine, borrower, operator):
    engine.set_operator(operator, True, sender=borrower)

    assert engine.is_operator(borrower, operator)
    assert not engine.is_operator(operator, borrower)

    logs = filter_logs(engine, "OperatorSet")
    assert len(logs) == 1
    assert logs[0].owner == borrower
    assert logs[0].operator == operator
    assert logs[0].approved is True


def test_set_operator_revokes(engine, borrower, operator):
    engine.set_operator(operator, True, sender=borrower)

    engine.set_operator(operator, False, sender=borrower)

    assert not engine.is_operator(borrower, operator)
    assert filter_logs(engine, "OperatorSet")[0].approved is False


def test_set_operator_zero_address_reverts(engine, borrower):
    with boa.reverts(dev="engine: operator is the zero address"):
        engine.set_operator(ZERO_ADDRESS, True, sender=borrower)


def test_operator_can_mint_on_behalf(engine, stablecoin, collateral_token, borrower, operator):
    """Money Flow: debt recorded on borrower, stablecoin -> operator."""
    deposit(engine, collateral_token, borrower, COLLATERAL)
    engine.set_operator(operator, True, sender=borrower)

    engine.mint(MIN_DEBT, borrower, operator, sender=operator)

    assert engine.address2minted(borrower) == MIN_DEBT
    assert engine.address2minted(operator) == 0
    assert stablecoin.balanceOf(operator) == MIN_DEBT

    logs = filter_logs(engine, "Mint")
    assert logs[0].caller == operator
    assert logs[0].user == borrower
    assert logs[0].receiver == operator


def test_operator_can_withdraw_on_behalf(engine, collateral_token, borrower, operator, receiver):
    """Money Flow: collateral engine -> receiver, debited from borrower."""
    deposit(engine, collateral_token, borrower, COLLATERAL)
    engine.set_operator(operator, True, sender=borrower)

    engine.withdraw(COLLATERAL, borrower, receiver, sender=operator)

    assert engine.address2deposit(borrower) == 0
    assert collateral_token.balanceOf(receiver) == COLLATERAL

    logs = filter_logs(engine, "Withdraw")
    assert logs[0].caller == operator
    assert logs[0].user == borrower
    assert logs[0].receiver == receiver


def test_operator_is_bound_by_min_collat_ratio(engine, collateral_token, borrower, operator):
    deposit(engine, collateral_token, borrower, COLLATERAL)
    engine.set_operator(operator, True, sender=borrower)

    with boa.reverts(dev="engine: below min collateral ratio"):
        engine.mint(COLLATERAL * 2_000, borrower, operator, sender=operator)


def test_revoked_operator_cannot_mint(engine, collateral_token, borrower, operator):
    deposit(engine, collateral_token, borrower, COLLATERAL)
    engine.set_operator(operator, True, sender=borrower)
    engine.set_operator(operator, False, sender=borrower)

    with boa.reverts(dev="engine: caller is not authorized"):
        engine.mint(MIN_DEBT, borrower, operator, sender=operator)


def test_operator_approval_is_scoped_per_owner(engine, collateral_token, borrower, operator, stranger):
    """Approval granted by `stranger` gives no rights over `borrower`'s position."""
    deposit(engine, collateral_token, borrower, COLLATERAL)
    engine.set_operator(operator, True, sender=stranger)

    with boa.reverts(dev="engine: caller is not authorized"):
        engine.withdraw(COLLATERAL, borrower, operator, sender=operator)


def test_operator_approval_is_not_transitive(engine, collateral_token, borrower, operator, stranger):
    deposit(engine, collateral_token, borrower, COLLATERAL)
    engine.set_operator(operator, True, sender=borrower)
    engine.set_operator(stranger, True, sender=operator)

    with boa.reverts(dev="engine: caller is not authorized"):
        engine.withdraw(COLLATERAL, borrower, stranger, sender=stranger)
