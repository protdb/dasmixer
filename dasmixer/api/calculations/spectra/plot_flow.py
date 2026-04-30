from .ion_match import IonMatchParameters, match_predictions, get_matches_dataframe
from .plot_matches import generate_spectrum_plot
from typing import Any
from dasmixer.utils.logger import logger


def make_full_spectrum_plot(
        params: dict | IonMatchParameters,
        mz: list[float],
        intensity: list[float],
        charges: list[int] | int,
        sequences: str | list[str] | None,
        headers: list[str] | str,
        spectrum_info: Any
):
    logger.debug(spectrum_info)
    if type(params) is dict:
        params = IonMatchParameters(**params)
    if type(sequences) is not list:
        if sequences is None:
            sequences = ['']
        else:
            sequences = [sequences]
    dfs = []
    for seq in sequences:
        pred = match_predictions(params, mz, intensity, charges, seq)
        dfs.append(
            get_matches_dataframe(
                pred, mz, intensity
            )
        )
    return generate_spectrum_plot(
        headers,
        dfs
    )