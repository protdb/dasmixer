from itertools import product

from dasmixer.utils.logger import logger


def get_leucine_combinations(seq: str, max_positions=7) -> list[str]:
    # Находим позиции всех I и L
    positions = [i for i, c in enumerate(seq) if c in "IL"]
    if len(positions) > max_positions:
        return [seq]

    variants = []
    # Перебираем все комбинации замен: на каждой позиции либо I, либо L
    for combo in product("IL", repeat=len(positions)):
        s = list(seq)
        for pos, char in zip(positions, combo):
            s[pos] = char
        variants.append("".join(s))
    logger.debug("get_leucine_combinations seq=%s variants=%s", seq, variants)
    return variants