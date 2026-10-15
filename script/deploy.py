from moccasin.boa_tools import VyperContract
from src import engine, factory, stable


def deploy() -> VyperContract:
    stable_blueprint: VyperContract = stable.deploy_as_blueprint()
    print(f"Deployed stable blueprint at: {stable_blueprint.address}")

    engine_blueprint: VyperContract = engine.deploy_as_blueprint()
    print(f"Deployed engine blueprint at: {engine_blueprint.address}")

    factory_contract: VyperContract = factory.deploy(
        stable_blueprint.address,
        engine_blueprint.address,
    )
    print(f"Deployed factory at: {factory_contract.address}")

    return factory_contract


def moccasin_main() -> VyperContract:
    return deploy()
