# pragma version ~=0.4.3
# pragma nonreentrancy on
"""
@title `factory` Stablecoin Engine Factory
@custom:contract-name factory
@license GNU Affero General Public License v3.0 only
@author rafael-abuawad
"""

from ethereum.ercs import IERC20
from interfaces import IOracle
from . import stable
from snekmate.auth import ownable as ow
from snekmate.auth import ownable_2step as ow2


initializes: ow
initializes: ow2[ownable := ow]
exports: ow2.__interface__


# @dev Stores the address of the `stable` blueprint
# used to deploy new stablecoins.
STABLE_BLUEPRINT: immutable(address)


# @dev Stores the address of the `engine` blueprint
# used to deploy new stability engines.
ENGINE_BLUEPRINT: immutable(address)


# @dev Returns the stablecoin `address` controlled by
# an engine `address` deployed by this factory. This
# is the zero address for unknown engines.
engine_to_stable: public(HashMap[address, address])


# @dev Returns the engine `address` that owns a
# stablecoin `address` deployed by this factory. This
# is the zero address for unknown stablecoins.
stable_to_engine: public(HashMap[address, address])


# @dev Returns the engine `address` at a given
# deployment index, starting at zero.
engines: public(HashMap[uint256, address])


# @dev Returns the number of engines deployed by
# this factory. Valid indices into `engines` are
# in the range `[0, engine_count)`.
engine_count: public(uint256)


# @dev Emitted when a new `engine` and its paired
# `stablecoin` are deployed via `deploy`.
event EngineDeployed:
    engine: indexed(address)
    stablecoin: indexed(address)
    collateral: indexed(address)
    oracle: address
    name: String[25]
    symbol: String[5]


@deploy
def __init__(stable_blueprint: address, engine_blueprint: address):
    assert stable_blueprint != empty(address)  # dev: factory: stable blueprint is the zero address
    assert engine_blueprint != empty(address)  # dev: factory: engine blueprint is the zero address

    ow.__init__()
    ow2.__init__()

    STABLE_BLUEPRINT = stable_blueprint
    ENGINE_BLUEPRINT = engine_blueprint


@external
@view
def stable_blueprint() -> address:
    return STABLE_BLUEPRINT


@external
@view
def engine_blueprint() -> address:
    return ENGINE_BLUEPRINT


@external
def deploy(
    collateral: IERC20,
    name: String[25],
    symbol: String[5],
    decimals: uint8,
    oracle: IOracle,
    min_collat_ratio: uint256,
    max_oracle_delay: uint256,
    min_debt: uint256,
) -> (address, address):
    ow._check_owner()
    assert collateral.address != empty(address)  # dev: factory: collateral is the zero address
    assert oracle.address != empty(address)  # dev: factory: oracle is the zero address
    assert decimals <= 18  # dev: factory: stablecoin decimals exceed 18

    stable_addr: address = create_from_blueprint(
        STABLE_BLUEPRINT,
        name,
        symbol,
        decimals,
        code_offset=3,
    )
    engine_addr: address = create_from_blueprint(
        ENGINE_BLUEPRINT,
        collateral,
        stable_addr,
        oracle,
        min_collat_ratio,
        max_oracle_delay,
        min_debt,
        code_offset=3,
    )

    extcall stable.__at__(stable_addr).transfer_ownership(engine_addr)

    index: uint256 = self.engine_count
    self.engines[index] = engine_addr
    self.engine_count = index + 1
    self.engine_to_stable[engine_addr] = stable_addr
    self.stable_to_engine[stable_addr] = engine_addr

    log EngineDeployed(
        engine=engine_addr,
        stablecoin=stable_addr,
        collateral=collateral.address,
        oracle=oracle.address,
        name=name,
        symbol=symbol,
    )
    return stable_addr, engine_addr
