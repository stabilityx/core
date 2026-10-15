import boa

from tests.utils.constants import MAX_ORACLE_DELAY, MIN_COLLAT_RATIO, MIN_DEBT, ZERO_ADDRESS
from tests.utils.helpers import deposit, filter_logs, open_position

COLLATERAL = 3 * 10**18  # 3 WETH @ 2000 = 6000 mUSD of value
MAX_DEBT = 4_000 * 10**18  # 6000 / 1.5


def test_mint_increases_debt_and_balance(engine, stablecoin, collateral_token, borrower):
    """Money Flow: freshly minted stablecoin -> borrower, debt recorded on borrower."""
    # ================= Setup =================
    deposit(engine, collateral_token, borrower, COLLATERAL)
    amount = 1_000 * 10**18

    # ================= Execute =================
    engine.mint(amount, sender=borrower)

    # ================= Verify state, logs, money flows =================
    assert engine.address2minted(borrower) == amount
    assert stablecoin.balanceOf(borrower) == amount
    assert stablecoin.totalSupply() == amount

    logs = filter_logs(engine, "Mint")
    assert len(logs) == 1
    assert logs[0].caller == borrower
    assert logs[0].user == borrower
    assert logs[0].receiver == borrower
    assert logs[0].amount == amount


def test_mint_to_receiver(engine, stablecoin, collateral_token, borrower, receiver):
    deposit(engine, collateral_token, borrower, COLLATERAL)

    engine.mint(MIN_DEBT, borrower, receiver, sender=borrower)

    assert engine.address2minted(borrower) == MIN_DEBT
    assert engine.address2minted(receiver) == 0
    assert stablecoin.balanceOf(receiver) == MIN_DEBT
    assert stablecoin.balanceOf(borrower) == 0
    assert filter_logs(engine, "Mint")[0].receiver == receiver


def test_mint_accumulates(engine, stablecoin, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)

    engine.mint(MIN_DEBT, sender=borrower)
    engine.mint(MIN_DEBT, sender=borrower)

    assert engine.address2minted(borrower) == 2 * MIN_DEBT
    assert stablecoin.balanceOf(borrower) == 2 * MIN_DEBT


def test_mint_up_to_exact_min_collat_ratio(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)

    engine.mint(MAX_DEBT, sender=borrower)

    assert engine.collat_ratio(borrower) == MIN_COLLAT_RATIO


def test_mint_above_min_collat_ratio_reverts(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)

    with boa.reverts(dev="engine: below min collateral ratio"):
        engine.mint(MAX_DEBT + 1, sender=borrower)


def test_mint_incrementally_above_min_collat_ratio_reverts(engine, collateral_token, borrower):
    open_position(engine, collateral_token, borrower, COLLATERAL, MAX_DEBT)

    with boa.reverts(dev="engine: below min collateral ratio"):
        engine.mint(1, sender=borrower)


def test_mint_without_collateral_reverts(engine, borrower):
    with boa.reverts(dev="engine: below min collateral ratio"):
        engine.mint(MIN_DEBT, sender=borrower)


def test_mint_exactly_min_debt(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)

    engine.mint(MIN_DEBT, sender=borrower)

    assert engine.address2minted(borrower) == MIN_DEBT


def test_mint_below_min_debt_reverts(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)

    with boa.reverts(dev="engine: debt below minimum"):
        engine.mint(MIN_DEBT - 1, sender=borrower)


def test_mint_small_amount_on_top_of_existing_debt(engine, collateral_token, borrower):
    """The floor applies to total debt, not to each individual mint."""
    open_position(engine, collateral_token, borrower, COLLATERAL, MIN_DEBT)

    engine.mint(1, sender=borrower)

    assert engine.address2minted(borrower) == MIN_DEBT + 1


def test_mint_zero_amount_reverts(engine, borrower):
    with boa.reverts(dev="engine: amount must be greater than zero"):
        engine.mint(0, sender=borrower)


def test_mint_to_zero_address_reverts(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)

    with boa.reverts(dev="engine: receiver is the zero address"):
        engine.mint(MIN_DEBT, borrower, ZERO_ADDRESS, sender=borrower)


def test_mint_unauthorized_reverts(engine, collateral_token, borrower, stranger):
    deposit(engine, collateral_token, borrower, COLLATERAL)

    with boa.reverts(dev="engine: caller is not authorized"):
        engine.mint(MIN_DEBT, borrower, stranger, sender=stranger)


# ================= Oracle failure modes =================


def test_mint_with_stale_oracle_reverts(engine, collateral_token, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)
    boa.env.time_travel(seconds=MAX_ORACLE_DELAY + 1)

    with boa.reverts(dev="engine: stale oracle price"):
        engine.mint(MIN_DEBT, sender=borrower)


def test_mint_at_oracle_staleness_boundary(engine, collateral_token, oracle, borrower):
    """`block.timestamp == updated_at + MAX_ORACLE_DELAY` is still fresh."""
    deposit(engine, collateral_token, borrower, COLLATERAL)
    oracle.set_timestamp(boa.env.timestamp - MAX_ORACLE_DELAY)

    engine.mint(MIN_DEBT, sender=borrower)

    assert engine.address2minted(borrower) == MIN_DEBT


def test_mint_with_future_oracle_timestamp(engine, collateral_token, oracle, borrower):
    """A feed reporting a future timestamp is treated as fresh rather than underflowing."""
    deposit(engine, collateral_token, borrower, COLLATERAL)
    oracle.set_timestamp(boa.env.timestamp + 10 * MAX_ORACLE_DELAY)

    engine.mint(MIN_DEBT, sender=borrower)

    assert engine.address2minted(borrower) == MIN_DEBT


def test_mint_with_never_updated_oracle_reverts(engine, collateral_token, oracle, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)
    oracle.set_timestamp(0)

    with boa.reverts(dev="engine: oracle never updated"):
        engine.mint(MIN_DEBT, sender=borrower)


def test_mint_with_zero_oracle_price_reverts(engine, collateral_token, oracle, borrower):
    deposit(engine, collateral_token, borrower, COLLATERAL)
    oracle.set_answer(0)

    with boa.reverts(dev="engine: invalid oracle price"):
        engine.mint(MIN_DEBT, sender=borrower)
