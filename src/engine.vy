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

PRECISION: constant(uint256) = 10**18
MIN_COLLAT_RATIO: public(constant(uint256)) = 15 * 10**17
LIQUIDATION_BONUS: public(constant(uint256)) = 10**17

COLLATERAL: immutable(IERC20)
COLLATERAL_DECIMALS: immutable(uint8)
COLLATERAL_SCALE: immutable(uint256)
STABLECOIN: immutable(stable.__interface__)
ORACLE: immutable(IOracle)

address2deposit: public(HashMap[address, uint256])
address2minted: public(HashMap[address, uint256])
is_operator: public(HashMap[address, HashMap[address, bool]])


event OperatorSet:
    owner: indexed(address)
    operator: indexed(address)
    approved: bool


event Deposit:
    caller: indexed(address)
    user: indexed(address)
    amount: uint256


event Withdraw:
    caller: indexed(address)
    user: indexed(address)
    receiver: indexed(address)
    amount: uint256


event Mint:
    caller: indexed(address)
    user: indexed(address)
    receiver: indexed(address)
    amount: uint256


event Burn:
    caller: indexed(address)
    user: indexed(address)
    amount: uint256


event Liquidate:
    user: indexed(address)
    liquidator: indexed(address)
    debt_burned: uint256
    collateral_seized: uint256


@deploy
def __init__(collateral: IERC20, stablecoin: stable.__interface__, oracle: IOracle):
    assert collateral.address != empty(address)  # dev: engine: collateral is the zero address
    assert stablecoin.address != empty(address)  # dev: engine: stablecoin is the zero address
    assert oracle.address != empty(address)  # dev: engine: oracle is the zero address

    collateral_decimals: uint8 = staticcall IERC20Detailed(collateral.address).decimals()
    assert collateral_decimals <= 18  # dev: engine: collateral decimals exceed 18

    COLLATERAL = collateral
    COLLATERAL_DECIMALS = collateral_decimals
    COLLATERAL_SCALE = 10 ** convert(18 - collateral_decimals, uint256)
    STABLECOIN = stablecoin
    ORACLE = oracle


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
def oracle() -> address:
    return ORACLE.address


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
    assert extcall COLLATERAL.transferFrom(msg.sender, self, amount)  # dev: engine: transfer failed
    log Deposit(caller=msg.sender, user=on_behalf_of, amount=amount)


@external
def burn(amount: uint256, on_behalf_of: address = msg.sender):
    assert amount > 0  # dev: engine: amount must be greater than zero
    assert on_behalf_of != empty(address)  # dev: engine: user is the zero address
    self.address2minted[on_behalf_of] -= amount
    extcall STABLECOIN.burn(msg.sender, amount)
    log Burn(caller=msg.sender, user=on_behalf_of, amount=amount)


@external
def mint(amount: uint256, on_behalf_of: address = msg.sender, receiver: address = msg.sender):
    assert amount > 0  # dev: engine: amount must be greater than zero
    assert receiver != empty(address)  # dev: engine: receiver is the zero address
    self._check_authorized(on_behalf_of)
    self.address2minted[on_behalf_of] += amount
    assert self._collat_ratio(on_behalf_of, self._oracle_price()) >= MIN_COLLAT_RATIO  # dev: engine: below min collateral ratio
    extcall STABLECOIN.mint(receiver, amount)
    log Mint(caller=msg.sender, user=on_behalf_of, receiver=receiver, amount=amount)


@external
def withdraw(amount: uint256, on_behalf_of: address = msg.sender, receiver: address = msg.sender):
    assert amount > 0  # dev: engine: amount must be greater than zero
    assert receiver != empty(address)  # dev: engine: receiver is the zero address
    self._check_authorized(on_behalf_of)
    self.address2deposit[on_behalf_of] -= amount
    assert self._collat_ratio(on_behalf_of, self._oracle_price()) >= MIN_COLLAT_RATIO  # dev: engine: below min collateral ratio
    assert extcall COLLATERAL.transfer(receiver, amount)  # dev: engine: transfer failed
    log Withdraw(caller=msg.sender, user=on_behalf_of, receiver=receiver, amount=amount)


@external
def liquidate(user: address, debt_to_cover: uint256 = max_value(uint256)):
    assert debt_to_cover > 0  # dev: engine: amount must be greater than zero
    oracle_value: uint256 = self._oracle_price()
    assert self._collat_ratio(user, oracle_value) < MIN_COLLAT_RATIO  # dev: engine: position is healthy

    user_debt: uint256 = self.address2minted[user]
    user_collateral: uint256 = self.address2deposit[user]
    actual_debt: uint256 = min(debt_to_cover, user_debt)

    seized_wad: uint256 = (actual_debt * (PRECISION + LIQUIDATION_BONUS)) // oracle_value
    collateral_seized: uint256 = seized_wad // COLLATERAL_SCALE

    if collateral_seized >= user_collateral:
        assert actual_debt == user_debt  # dev: engine: must liquidate full debt when underwater
        collateral_seized = user_collateral

    assert collateral_seized > 0  # dev: engine: collateral seized is zero

    self.address2minted[user] = user_debt - actual_debt
    self.address2deposit[user] = user_collateral - collateral_seized

    if actual_debt < user_debt:
        assert self._collat_ratio(user, oracle_value) >= MIN_COLLAT_RATIO  # dev: engine: partial liquidation must restore health

    extcall STABLECOIN.burn(msg.sender, actual_debt)
    assert extcall COLLATERAL.transfer(msg.sender, collateral_seized)  # dev: engine: transfer failed
    log Liquidate(
        user=user,
        liquidator=msg.sender,
        debt_burned=actual_debt,
        collateral_seized=collateral_seized,
    )


@external
@view
def collat_ratio(user: address) -> uint256:
    return self._collat_ratio(user, self._oracle_price())


@internal
@view
def _check_authorized(user: address):
    assert msg.sender == user or self.is_operator[user][msg.sender]  # dev: engine: caller is not authorized


@internal
@view
def _oracle_price() -> uint256:
    oracle_value: uint256 = staticcall ORACLE.latest_answer()
    assert oracle_value > 0  # dev: engine: invalid oracle price
    return oracle_value


@internal
@view
def _collat_ratio(user: address, oracle_value: uint256) -> uint256:
    minted: uint256 = self.address2minted[user]
    if minted == 0:
        return max_value(uint256)

    normalized_deposit: uint256 = self.address2deposit[user] * COLLATERAL_SCALE
    total_value: uint256 = (normalized_deposit * oracle_value) // PRECISION
    return (total_value * PRECISION) // minted
