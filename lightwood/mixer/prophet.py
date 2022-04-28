from typing import Dict, Union

from lightwood.mixer.sktime import SkTime


class ProphetMixer(SkTime):
    def __init__(self,
                 stop_after: float,
                 target: str,
                 dtype_dict: Dict[str, str],
                 n_ts_predictions: int,
                 ts_analysis: Dict,
                 model_path: str = 'fbprophet.Prophet',
                 auto_size: bool = True,
                 hyperparam_search: bool = False,
                 target_transforms: Dict[str, Union[int, str]] = {}
                 ):
        super().__init__(stop_after, target, dtype_dict, n_ts_predictions, ts_analysis,
                         model_path, auto_size, hyperparam_search, target_transforms)
        self.stable = False
        self.model_path = model_path
        self.possible_models = [self.model_path]
        self.n_trials = len(self.possible_models)
