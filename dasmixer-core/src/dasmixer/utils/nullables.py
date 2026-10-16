import numpy as np
import pandas as pd

class Nullables:
    """
    Utility functions for data representations containing NaN values.
    """

    @staticmethod
    def bool_column(column: pd.Series, return_str = False) -> pd.Series:
        if return_str:
            true_val = '✓'
            false_val = ''
        else:
            true_val = True
            false_val = False
        def _run(x):
            if not x:
                return false_val
            if type(x) is float and np.isnan(x):
                return false_val
            return true_val
        return column.apply(_run)

    @staticmethod
    def int_column(column: pd.Series, np_to_none=True, to_string=False) -> pd.Series:
        if np_to_none:
            if to_string:
                ret_none = ''
            else:
                ret_none = None
        else:
            ret_none = 0
        def _run(x):
            if x is None:
                return ret_none
            if type(x) is float and np.isnan(x):
                return ret_none
            try:
                return int(x)
            except ValueError:
                return x
        if not to_string:
            return column.apply(_run)
        return column.apply(lambda x: str(_run(x)))
