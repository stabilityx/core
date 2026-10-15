# pragma version ~=0.4.3
# pragma nonreentrancy on
"""
@title `engine` Stablecoin Stability Engine
@custom:contract-name engine
@license GNU Affero General Public License v3.0 only
@author rafael-abuawad
"""

from ethereum.ercs import IERC20
from ethereum.ercs import IERC20Detailed
from interfaces import IOracle
from . import stable


# @dev The fixed-point precision used for all internal
# accounting. Collateral amounts, debt amounts, oracle
# prices, and collateral ratios are normalised to 18
# decimals before any arithmetic is performed.
PRECISION: constant(uint256) = 10**18


# @dev The smallest value `MIN_COLLAT_RATIO` may be
# configured to at deployment, i.e. 135%.
MIN_COLLAT_RATIO_LOWER_BOUND: constant(uint256) = 135 * 10**16


# @dev The largest value `MIN_COLLAT_RATIO` may be
# configured to at deployment, i.e. 200%.
MIN_COLLAT_RATIO_UPPER_BOUND: constant(uint256) = 200 * 10**16


# @dev Returns the bonus, in `PRECISION` units, paid
# to a liquidator on top of the collateral value of
# the debt they cover, i.e. 10%.
LIQUIDATION_BONUS: public(constant(uint256)) = 10**17


# @dev The smallest value `MAX_ORACLE_DELAY` may be
# configured to at deployment, i.e. one hour.
# @notice Oracle heartbeats vary per feed, so the
# tolerated staleness window is set per engine. The
# bounds keep it loose enough for slow feeds and tight
# enough that a frozen feed cannot be used indefinitely.
MAX_ORACLE_DELAY_LOWER_BOUND: constant(uint256) = 60 * 60


# @dev The largest value `MAX_ORACLE_DELAY` may be
# configured to at deployment, i.e. seven days.
# @notice See comment on the staleness window above
# at `MAX_ORACLE_DELAY_LOWER_BOUND`.
MAX_ORACLE_DELAY_UPPER_BOUND: constant(uint256) = 7 * 24 * 60 * 60


# @dev The smallest value `MIN_DEBT` may be configured
# to at deployment, denominated in 18 decimals.
# @notice Positions smaller than the debt floor are not
# worth the gas to liquidate and would otherwise linger
# as bad debt.
MIN_DEBT_LOWER_BOUND: constant(uint256) = 10**18


# @dev The largest value `MIN_DEBT` may be configured
# to at deployment, denominated in 18 decimals.
# @notice See comment on the debt floor above at
# `MIN_DEBT_LOWER_BOUND`.
MIN_DEBT_UPPER_BOUND: constant(uint256) = 10**4 * 10**18


# @dev Stores the ERC-20 token accepted as collateral.
# @notice Exposed via the `collateral` function.
COLLATERAL: immutable(IERC20)


# @dev Stores the decimal places of the collateral
# token, read from the token at deployment.
# @notice Exposed via the `collateral_decimals`
# function.
COLLATERAL_DECIMALS: immutable(uint8)


# @dev Stores the factor that scales a raw collateral
# amount up to 18 decimals, i.e.
# `10 ** (18 - COLLATERAL_DECIMALS)`.
COLLATERAL_SCALE: immutable(uint256)


# @dev Stores the stablecoin minted and burned by
# this engine. The engine is the stablecoin's owner.
# @notice Exposed via the `stablecoin` function.
STABLECOIN: immutable(stable.__interface__)


# @dev Stores the decimal places of the stablecoin,
# read from the token at deployment.
# @notice Exposed via the `stablecoin_decimals`
# function.
STABLECOIN_DECIMALS: immutable(uint8)


# @dev Stores the factor that scales a raw stablecoin
# amount up to 18 decimals, i.e.
# `10 ** (18 - STABLECOIN_DECIMALS)`.
STABLECOIN_SCALE: immutable(uint256)


# @dev Stores the price feed that quotes the value
# of one unit of collateral in stablecoin terms.
# @notice Exposed via the `oracle` function.
ORACLE: immutable(IOracle)


# @dev Stores the factor that scales a raw oracle
# answer up to 18 decimals, i.e.
# `10 ** (18 - oracle.decimals())`.
ORACLE_SCALE: immutable(uint256)


# @dev Returns the minimum collateral ratio, in
# `PRECISION` units, a position must maintain to
# mint or withdraw. Positions below this ratio can
# be liquidated. Bounded by `MIN_COLLAT_RATIO_LOWER_BOUND`
# and `MIN_COLLAT_RATIO_UPPER_BOUND`.
MIN_COLLAT_RATIO: public(immutable(uint256))


# @dev Returns the maximum age, in seconds, of an
# oracle answer before it is considered stale.
# Bounded by `MAX_ORACLE_DELAY_LOWER_BOUND` and
# `MAX_ORACLE_DELAY_UPPER_BOUND`.
MAX_ORACLE_DELAY: public(immutable(uint256))


# @dev Returns the minimum non-zero debt, denominated
# in 18 decimals, a position may carry. Bounded by
# `MIN_DEBT_LOWER_BOUND` and `MIN_DEBT_UPPER_BOUND`.
MIN_DEBT: public(immutable(uint256))


# @dev Returns the amount of collateral, in the
# collateral token's native decimals, deposited
# for an `address`.
address2deposit: public(HashMap[address, uint256])


# @dev Returns the amount of stablecoin debt, in the
# stablecoin's native decimals, owed by an `address`.
address2minted: public(HashMap[address, uint256])


# @dev Returns `True` if an `operator` has been
# approved by an `owner` to mint and withdraw on
# their behalf. This is `False` by default. This
# value changes when `set_operator` is called.
is_operator: public(HashMap[address, HashMap[address, bool]])


# @dev Emitted when an `owner` approves or revokes
# an `operator` via `set_operator`.
event OperatorSet:
    owner: indexed(address)
    operator: indexed(address)
    approved: bool


# @dev Emitted when a `caller` deposits `amount` of
# collateral into the position of `user`.
event Deposit:
    caller: indexed(address)
    user: indexed(address)
    amount: uint256


# @dev Emitted when a `caller` withdraws `amount` of
# collateral from the position of `user` and sends
# it to `receiver`.
event Withdraw:
    caller: indexed(address)
    user: indexed(address)
    receiver: indexed(address)
    amount: uint256


# @dev Emitted when a `caller` mints `amount` of
# stablecoin against the position of `user` and
# sends it to `receiver`.
event Mint:
    caller: indexed(address)
    user: indexed(address)
    receiver: indexed(address)
    amount: uint256


# @dev Emitted when a `caller` burns `amount` of
# their own stablecoin to repay the debt of `user`.
event Burn:
    caller: indexed(address)
    user: indexed(address)
    amount: uint256


# @dev Emitted when a `liquidator` repays `debt_burned`
# of the debt of an undercollateralised `user` and
# seizes `collateral_seized` of their collateral,
# including the `LIQUIDATION_BONUS`.
event Liquidate:
    user: indexed(address)
    liquidator: indexed(address)
    debt_burned: uint256
    collateral_seized: uint256


@deploy
def __init__(
    collateral: IERC20,
    stablecoin: stable.__interface__,
    oracle: IOracle,
    min_collat_ratio: uint256,
    max_oracle_delay: uint256,
    min_debt: uint256,
):
    assert collateral.address != empty(address)  # dev: engine: collateral is the zero address
    assert stablecoin.address != empty(address)  # dev: engine: stablecoin is the zero address
    assert oracle.address != empty(address)  # dev: engine: oracle is the zero address
    assert (
        min_collat_ratio >= MIN_COLLAT_RATIO_LOWER_BOUND
        and min_collat_ratio <= MIN_COLLAT_RATIO_UPPER_BOUND
    )  # dev: engine: invalid min collateral ratio
    assert (
        max_oracle_delay >= MAX_ORACLE_DELAY_LOWER_BOUND
        and max_oracle_delay <= MAX_ORACLE_DELAY_UPPER_BOUND
    )  # dev: engine: invalid max oracle delay
    assert (
        min_debt >= MIN_DEBT_LOWER_BOUND and min_debt <= MIN_DEBT_UPPER_BOUND
    )  # dev: engine: invalid min debt

    collateral_decimals: uint8 = staticcall IERC20Detailed(collateral.address).decimals()
    assert collateral_decimals <= 18  # dev: engine: collateral decimals exceed 18

    stablecoin_decimals: uint8 = staticcall IERC20Detailed(stablecoin.address).decimals()
    assert stablecoin_decimals <= 18  # dev: engine: stablecoin decimals exceed 18

    oracle_decimals: uint8 = staticcall oracle.decimals()
    assert oracle_decimals <= 18  # dev: engine: oracle decimals exceed 18

    COLLATERAL = collateral
    COLLATERAL_DECIMALS = collateral_decimals
    COLLATERAL_SCALE = 10 ** convert(18 - collateral_decimals, uint256)

    STABLECOIN = stablecoin
    STABLECOIN_DECIMALS = stablecoin_decimals
    STABLECOIN_SCALE = 10 ** convert(18 - stablecoin_decimals, uint256)

    ORACLE = oracle
    ORACLE_SCALE = 10 ** convert(18 - oracle_decimals, uint256)

    MIN_COLLAT_RATIO = min_collat_ratio
    MAX_ORACLE_DELAY = max_oracle_delay
    MIN_DEBT = min_debt

    # Sanity-check the feed at deploy time so a misconfigured oracle fails here
    # rather than silently bricking the engine once it holds collateral.
    assert self._oracle_price() > 0  # dev: engine: invalid oracle price


@external
@view
def collateral() -> address:
    return COLLATERAL.address


@external
@view
def collateral_decimals() -> uint8:
    return COLLATERAL_DECIMALS


@external
@view
def stablecoin() -> address:
    return STABLECOIN.address


@external
@view
def stablecoin_decimals() -> uint8:
    return STABLECOIN_DECIMALS


@external
@view
def oracle() -> address:
    return ORACLE.address


@external
@view
def collat_ratio(user: address) -> uint256:
    if self.address2minted[user] == 0:
        return max_value(uint256)
    return self._collat_ratio(user, self._oracle_price())


@external
def set_operator(operator: address, approved: bool):
    assert operator != empty(address)  # dev: engine: operator is the zero address
    self.is_operator[msg.sender][operator] = approved
    log OperatorSet(owner=msg.sender, operator=operator, approved=approved)


@external
def deposit(amount: uint256, on_behalf_of: address = msg.sender):
    assert amount > 0  # dev: engine: amount must be greater than zero
    assert on_behalf_of != empty(address)  # dev: engine: user is the zero address
    self.address2deposit[on_behalf_of] += amount
    assert extcall COLLATERAL.transferFrom(msg.sender, self, amount, default_return_value=True)  # dev: engine: transfer failed
    log Deposit(caller=msg.sender, user=on_behalf_of, amount=amount)


@external
def burn(amount: uint256, on_behalf_of: address = msg.sender):
    assert amount > 0  # dev: engine: amount must be greater than zero
    assert on_behalf_of != empty(address)  # dev: engine: user is the zero address
    self.address2minted[on_behalf_of] -= amount
    self._assert_debt_floor(on_behalf_of)
    extcall STABLECOIN.burn(msg.sender, amount)
    log Burn(caller=msg.sender, user=on_behalf_of, amount=amount)


@external
def mint(amount: uint256, on_behalf_of: address = msg.sender, receiver: address = msg.sender):
    assert amount > 0  # dev: engine: amount must be greater than zero
    assert receiver != empty(address)  # dev: engine: receiver is the zero address
    self._check_authorized(on_behalf_of)
    self.address2minted[on_behalf_of] += amount
    self._assert_debt_floor(on_behalf_of)
    self._assert_healthy(on_behalf_of)
    extcall STABLECOIN.mint(receiver, amount)
    log Mint(caller=msg.sender, user=on_behalf_of, receiver=receiver, amount=amount)


@external
def withdraw(amount: uint256, on_behalf_of: address = msg.sender, receiver: address = msg.sender):
    assert amount > 0  # dev: engine: amount must be greater than zero
    assert receiver != empty(address)  # dev: engine: receiver is the zero address
    self._check_authorized(on_behalf_of)
    self.address2deposit[on_behalf_of] -= amount
    self._assert_healthy(on_behalf_of)
    assert extcall COLLATERAL.transfer(receiver, amount, default_return_value=True)  # dev: engine: transfer failed
    log Withdraw(caller=msg.sender, user=on_behalf_of, receiver=receiver, amount=amount)


@external
def liquidate(user: address, debt_to_cover: uint256 = max_value(uint256)):
    assert debt_to_cover > 0  # dev: engine: amount must be greater than zero
    oracle_value: uint256 = self._oracle_price()
    assert self._collat_ratio(user, oracle_value) < MIN_COLLAT_RATIO  # dev: engine: position is healthy

    user_debt: uint256 = self.address2minted[user]
    user_collateral: uint256 = self.address2deposit[user]
    actual_debt: uint256 = min(debt_to_cover, user_debt)

    normalized_debt: uint256 = actual_debt * STABLECOIN_SCALE
    seized_wad: uint256 = (normalized_debt * (PRECISION + LIQUIDATION_BONUS)) // oracle_value
    collateral_seized: uint256 = seized_wad // COLLATERAL_SCALE

    if collateral_seized >= user_collateral:
        assert actual_debt == user_debt  # dev: engine: must liquidate full debt when underwater
        collateral_seized = user_collateral

    assert collateral_seized > 0  # dev: engine: collateral seized is zero

    self.address2minted[user] = user_debt - actual_debt
    self.address2deposit[user] = user_collateral - collateral_seized

    if actual_debt < user_debt:
        assert self._collat_ratio(user, oracle_value) >= MIN_COLLAT_RATIO  # dev: engine: partial liquidation must restore health
        self._assert_debt_floor(user)

    extcall STABLECOIN.burn(msg.sender, actual_debt)
    assert extcall COLLATERAL.transfer(msg.sender, collateral_seized, default_return_value=True)  # dev: engine: transfer failed
    log Liquidate(
        user=user,
        liquidator=msg.sender,
        debt_burned=actual_debt,
        collateral_seized=collateral_seized,
    )


@internal
@view
def _check_authorized(user: address):
    assert msg.sender == user or self.is_operator[user][msg.sender]  # dev: engine: caller is not authorized


@internal
@view
def _assert_healthy(user: address):
    # A debt-free position is always healthy, so the oracle is never consulted.
    # This keeps deposits withdrawable even if the oracle is broken or deprecated.
    if self.address2minted[user] == 0:
        return
    assert self._collat_ratio(user, self._oracle_price()) >= MIN_COLLAT_RATIO  # dev: engine: below min collateral ratio


@internal
@view
def _assert_debt_floor(user: address):
    minted: uint256 = self.address2minted[user]
    if minted == 0:
        return
    assert minted * STABLECOIN_SCALE >= MIN_DEBT  # dev: engine: debt below minimum


@internal
@view
def _oracle_price() -> uint256:
    updated_at: uint256 = staticcall ORACLE.latest_timestamp()
    assert updated_at > 0  # dev: engine: oracle never updated
    # Written this way rather than `block.timestamp - updated_at` so that a feed
    # reporting a future timestamp is treated as fresh instead of reverting.
    assert block.timestamp <= updated_at + MAX_ORACLE_DELAY  # dev: engine: stale oracle price

    oracle_value: uint256 = staticcall ORACLE.latest_answer()
    assert oracle_value > 0  # dev: engine: invalid oracle price
    return oracle_value * ORACLE_SCALE


@internal
@view
def _collat_ratio(user: address, oracle_value: uint256) -> uint256:
    minted: uint256 = self.address2minted[user]
    if minted == 0:
        return max_value(uint256)

    normalized_deposit: uint256 = self.address2deposit[user] * COLLATERAL_SCALE
    normalized_minted: uint256 = minted * STABLECOIN_SCALE
    total_value: uint256 = (normalized_deposit * oracle_value) // PRECISION
    return (total_value * PRECISION) // normalized_minted
