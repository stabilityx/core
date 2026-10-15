# pragma version ~=0.4.3
"""
@title Mock ERC-20 Collateral Token
@custom:contract-name MockERC20
@license GNU Affero General Public License v3.0 only
@notice Test-only token with configurable decimals, a
        toggle to make transfers return `False`, and an
        optional callback fired on every transfer to
        simulate reentrant (e.g. ERC-777 style) tokens.
"""

from ethereum.ercs import IERC20
implements: IERC20


event Transfer:
    sender: indexed(address)
    receiver: indexed(address)
    value: uint256


event Approval:
    owner: indexed(address)
    spender: indexed(address)
    value: uint256


name: public(String[32])
symbol: public(String[8])
decimals: public(uint8)
totalSupply: public(uint256)
balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])


# @dev When `True`, `transfer` and `transferFrom` return
# `False` without moving any funds.
return_false: public(bool)


# @dev When non-zero, every successful transfer performs
# `raw_call(callback_target, callback_data)` before
# returning. Reverts in the callback bubble up.
callback_target: public(address)
callback_data: public(Bytes[512])


@deploy
def __init__(name_: String[32], symbol_: String[8], decimals_: uint8):
    self.name = name_
    self.symbol = symbol_
    self.decimals = decimals_


@external
def mint(to: address, amount: uint256):
    self.balanceOf[to] += amount
    self.totalSupply += amount
    log Transfer(sender=empty(address), receiver=to, value=amount)


@external
def set_return_false(enabled: bool):
    self.return_false = enabled


@external
def set_callback(target: address, data: Bytes[512]):
    self.callback_target = target
    self.callback_data = data


@external
def approve(spender: address, amount: uint256) -> bool:
    self.allowance[msg.sender][spender] = amount
    log Approval(owner=msg.sender, spender=spender, value=amount)
    return True


@external
def transfer(to: address, amount: uint256) -> bool:
    if self.return_false:
        return False
    self._transfer(msg.sender, to, amount)
    return True


@external
def transferFrom(owner: address, to: address, amount: uint256) -> bool:
    if self.return_false:
        return False
    current: uint256 = self.allowance[owner][msg.sender]
    if current != max_value(uint256):
        self.allowance[owner][msg.sender] = current - amount
    self._transfer(owner, to, amount)
    return True


@internal
def _transfer(owner: address, to: address, amount: uint256):
    self.balanceOf[owner] -= amount
    self.balanceOf[to] += amount
    log Transfer(sender=owner, receiver=to, value=amount)
    if self.callback_target != empty(address):
        raw_call(self.callback_target, self.callback_data)
