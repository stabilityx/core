# pragma version ~=0.4.3
# pragma nonreentrancy on
"""
@title `stable` Stablecoin Module Implementation
@custom:contract-name stable
@license GNU Affero General Public License v3.0 only
@author rafael-abuawad
"""

from ethereum.ercs import IERC20
implements: IERC20


from ethereum.ercs import IERC20Detailed
implements: IERC20Detailed


from snekmate.tokens.interfaces import IERC20Permit
implements: IERC20Permit


from snekmate.utils.interfaces import IERC5267
implements: IERC5267


from snekmate.auth import ownable as ow
initializes: ow


from snekmate.tokens import erc20
initializes: erc20[ownable := ow]


exports: (
    erc20.IERC20,
    erc20.IERC20Detailed,
    erc20.IERC20Permit,
    erc20.IERC5267,
    ow.owner,
    ow.transfer_ownership,
)

EIP712_VERSION: constant(String[20]) = "1"


@deploy
@payable
def __init__(
    name_: String[25],
    symbol_: String[5],
    decimals_: uint8,
):
    ow.__init__()
    erc20.__init__(name_, symbol_, decimals_, name_, EIP712_VERSION)


@external
def mint(owner: address, amount: uint256):
    ow._check_owner()
    erc20._mint(owner, amount)


@external
def burn(owner: address, amount: uint256):
    ow._check_owner()
    erc20._burn(owner, amount)
