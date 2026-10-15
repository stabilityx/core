"""Pure-Python reference models of the integer math in `src/engine.vy`."""

from tests.utils.constants import LIQUIDATION_BONUS, MAX_UINT256, PRECISION


def scale(decimals: int) -> int:
    return 10 ** (18 - decimals)


def price_wad(answer: int, oracle_decimals: int) -> int:
    return answer * scale(oracle_decimals)


def collat_ratio(
    deposit: int,
    minted: int,
    answer: int,
    collateral_decimals: int,
    stable_decimals: int,
    oracle_decimals: int,
) -> int:
    if minted == 0:
        return MAX_UINT256
    normalized_deposit = deposit * scale(collateral_decimals)
    normalized_minted = minted * scale(stable_decimals)
    total_value = normalized_deposit * price_wad(answer, oracle_decimals) // PRECISION
    return total_value * PRECISION // normalized_minted


def collateral_seized(
    debt: int,
    answer: int,
    collateral_decimals: int,
    stable_decimals: int,
    oracle_decimals: int,
) -> int:
    """Uncapped collateral seized for covering `debt`, before the full-seizure cap."""
    normalized_debt = debt * scale(stable_decimals)
    seized_wad = normalized_debt * (PRECISION + LIQUIDATION_BONUS) // price_wad(answer, oracle_decimals)
    return seized_wad // scale(collateral_decimals)
