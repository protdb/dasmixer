from itertools import product


def get_leucine_combinations(seq: str) -> list[str]:
    # Находим позиции всех I и L
    positions = [i for i, c in enumerate(seq) if c in "IL"]

    variants = []
    # Перебираем все комбинации замен: на каждой позиции либо I, либо L
    for combo in product("IL", repeat=len(positions)):
        s = list(seq)
        for pos, char in zip(positions, combo):
            s[pos] = char
        variants.append("".join(s))

    return variants