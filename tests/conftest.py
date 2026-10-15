import boa
import pytest

from tests.mocks.deployers import MOCK_ERC20, MOCK_ORACLE
from tests.utils.constants import (
    COLLATERAL_DECIMALS,
    COLLATERAL_NAME,
    COLLATERAL_SYMBOL,
    INITIAL_PRICE,
    ORACLE_DECIMALS,
)
from tests.utils.deployers import (
    ENGINE_DEPLOYER,
    FACTORY_DEPLOYER,
    STABLE_DEPLOYER,
    deploy_market,
)

boa.env.enable_fast_mode()


# ================= Accounts =================


@pytest.fixture(scope="session")
def admin():
    return boa.env.generate_address("admin")


@pytest.fixture(scope="session")
def borrower():
    return boa.env.generate_address("borrower")


@pytest.fixture(scope="session")
def operator():
    return boa.env.generate_address("operator")


@pytest.fixture(scope="session")
def liquidator():
    return boa.env.generate_address("liquidator")


@pytest.fixture(scope="session")
def receiver():
    return boa.env.generate_address("receiver")


@pytest.fixture(scope="session")
def stranger():
    return boa.env.generate_address("stranger")


# ================= Mocks =================


@pytest.fixture(scope="module")
def collateral_token():
    return MOCK_ERC20.deploy(COLLATERAL_NAME, COLLATERAL_SYMBOL, COLLATERAL_DECIMALS)


@pytest.fixture(scope="module")
def oracle():
    return MOCK_ORACLE.deploy(ORACLE_DECIMALS, INITIAL_PRICE * 10**ORACLE_DECIMALS)


# ================= Protocol =================


@pytest.fixture(scope="module")
def stable_blueprint():
    return STABLE_DEPLOYER.deploy_as_blueprint()


@pytest.fixture(scope="module")
def engine_blueprint():
    return ENGINE_DEPLOYER.deploy_as_blueprint()


@pytest.fixture(scope="module")
def factory(admin, stable_blueprint, engine_blueprint):
    with boa.env.prank(admin):
        return FACTORY_DEPLOYER.deploy(stable_blueprint.address, engine_blueprint.address)


@pytest.fixture(scope="module")
def market(factory, admin, collateral_token, oracle):
    return deploy_market(factory, admin, collateral_token, oracle)


@pytest.fixture(scope="module")
def stablecoin(market):
    return market[0]


@pytest.fixture(scope="module")
def engine(market):
    return market[1]
