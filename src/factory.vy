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
initializes: ow


from snekmate.auth import ownable_2step as ow2
initializes: ow2[ownable := ow]
exports: ow2.__interface__


STABLE_BLUEPRINT: immutable(address)
ENGINE_BLUEPRINT: immutable(address)


engine_to_stable: public(HashMap[address, address])
stable_to_engine: public(HashMap[address, address])
engines: public(HashMap[uint256, address])
engine_count: public(uint256)


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
    oracle: IOracle,
) -> (address, address):
    ow._check_owner()
    assert collateral.address != empty(address)  # dev: factory: collateral is the zero address
    assert oracle.address != empty(address)  # dev: factory: oracle is the zero address

    stable_addr: address = create_from_blueprint(
        STABLE_BLUEPRINT,
        name,
        symbol,
        code_offset=3,
    )
    engine_addr: address = create_from_blueprint(
        ENGINE_BLUEPRINT,
        collateral,
        stable_addr,
        oracle,
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
