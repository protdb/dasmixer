from typing import Any

from dasmixer.utils.logger import logger

from .ion_match import IonMatchParameters, get_matches_dataframe, match_predictions
from .plot_matches import generate_spectrum_plot


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
    if len(sequences) == 0:
        dfs.append(get_matches_dataframe(None, mz, intensity))
    else:
        for seq in sequences:
            predictions = match_predictions(params, mz, intensity, charges, seq)
            dfs.append(
                get_matches_dataframe(
                    predictions, mz, intensity
                )
            )
    return generate_spectrum_plot(
        headers,
        dfs
    )