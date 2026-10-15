"""Production contract deployers and market helpers."""

import boa
from moccasin.boa_tools import VyperContract
from src import engine, factory, stable

from tests.utils.constants import (
    MAX_ORACLE_DELAY,
    MIN_COLLAT_RATIO,
    MIN_DEBT,
    STABLE_DECIMALS,
    STABLE_NAME,
    STABLE_SYMBOL,
)

ENGINE_DEPLOYER = engine
FACTORY_DEPLOYER = factory
STABLE_DEPLOYER = stable


def deploy_market(
    factory_contract: VyperContract,
    admin,
    collateral_token: VyperContract,
    oracle: VyperContract,
    *,
    name: str = STABLE_NAME,
    symbol: str = STABLE_SYMBOL,
    decimals: int = STABLE_DECIMALS,
    min_collat_ratio: int = MIN_COLLAT_RATIO,
    max_oracle_delay: int = MAX_ORACLE_DELAY,
    min_debt: int = MIN_DEBT,
) -> tuple[VyperContract, VyperContract]:
    """Deploy a stablecoin + engine pair through the factory. Returns (stablecoin, engine)."""
    stable_addr, engine_addr = factory_contract.deploy(
        collateral_token.address,
        name,
        symbol,
        decimals,
        oracle.address,
        min_collat_ratio,
        max_oracle_delay,
        min_debt,
        sender=admin,
    )
    return STABLE_DEPLOYER.at(stable_addr), ENGINE_DEPLOYER.at(engine_addr)


def deploy_engine_direct(
    collateral_token: VyperContract,
    oracle: VyperContract,
    *,
    stable_decimals: int = STABLE_DECIMALS,
    min_collat_ratio: int = MIN_COLLAT_RATIO,
    max_oracle_delay: int = MAX_ORACLE_DELAY,
    min_debt: int = MIN_DEBT,
    stablecoin_address=None,
) -> VyperContract:
    """Deploy an engine without the factory, e.g. to exercise constructor checks."""
    if stablecoin_address is None:
        stablecoin_address = STABLE_DEPLOYER.deploy(STABLE_NAME, STABLE_SYMBOL, stable_decimals).address
    return ENGINE_DEPLOYER.deploy(
        collateral_token.address,
        stablecoin_address,
        oracle.address,
        min_collat_ratio,
        max_oracle_delay,
        min_debt,
    )


def new_address(label: str) -> str:
    return boa.env.generate_address(label)
