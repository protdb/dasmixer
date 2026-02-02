import re

from pyteomics import mass


def calculate_ppm(sequence, pepmass, charge):
    """
    Рассчитывает PPM difference между экспериментальной и теоретической массой пептида

    Parameters:
    -----------
    sequence : str
        Последовательность пептида с модификациями, например:
        "(+42.01)ALDLERPR" - модификация на N-конце
        "EAM(+15.99)DTSSK" - окисление метионина
        "PEPTIDEC(+57.02)R" - карбамидометилирование цистеина
    pepmass : float
        Экспериментальное значение m/z из PEPMASS в MGF-файле
    charge : int
        Заряд иона

    Returns:
    --------
    float : PPM difference
    """

    # Парсинг последовательности и извлечение модификаций
    # Паттерн для поиска модификаций: (±число) или аминокислота(±число)
    mod_pattern = r'\(([+-]?\d*\.?\d*)\)'

    # Извлекаем все модификации из строки
    modifications = re.findall(mod_pattern, sequence)
    mod_masses = [float(m) for m in modifications]

    # Удаляем модификации из последовательности, оставляя только аминокислоты
    clean_sequence = re.sub(mod_pattern, '', sequence)

    # Рассчитываем базовую массу пептида
    theoretical_mz = mass.calculate_mass(
        sequence=clean_sequence,
        ion_type='M',
        charge=charge
    )

    # Добавляем массы модификаций
    total_mod_mass = sum(mod_masses)
    theoretical_mz += total_mod_mass / charge

    # Рассчитываем PPM
    ppm = ((pepmass - theoretical_mz) / theoretical_mz) * 1e6

    return ppm
