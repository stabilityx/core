from tests.utils.constants import MAX_UINT256


def filter_logs(contract, event_name: str) -> list:
    """Decoded logs of the last call on `contract` (including child calls) named `event_name`."""
    return [log for log in contract.get_logs() if type(log).__name__ == event_name]


def deposit(engine, collateral_token, user, amount: int, on_behalf_of=None):
    """Mint `amount` collateral to `user`, approve the engine, and deposit."""
    collateral_token.mint(user, amount)
    collateral_token.approve(engine.address, MAX_UINT256, sender=user)
    if on_behalf_of is None:
        engine.deposit(amount, sender=user)
    else:
        engine.deposit(amount, on_behalf_of, sender=user)


def open_position(engine, collateral_token, user, collateral_amount: int, debt_amount: int):
    """Deposit `collateral_amount` and mint `debt_amount` stablecoin to `user`."""
    deposit(engine, collateral_token, user, collateral_amount)
    engine.mint(debt_amount, sender=user)


def set_price(oracle, price, oracle_decimals: int | None = None):
    """Push a fresh oracle answer of `price` whole stablecoin units per whole collateral unit."""
    if oracle_decimals is None:
        oracle_decimals = oracle.decimals()
    oracle.set_answer(int(price * 10**oracle_decimals))
