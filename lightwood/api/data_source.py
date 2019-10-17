import importlib
import numpy as np
from torch.utils.data import Dataset
import random
from lightwood.config.config import CONFIG


class DataSource(Dataset):

    def __init__(self, data_frame, configuration):
        """
        Create a lightwood datasource from the data frame
        :param data_frame:
        :param configuration
        """

        self.data_frame = data_frame
        self.configuration = configuration
        self.encoders = {}
        self.transformer = None
        self.training = False # Flip this flag if you are using the datasource while training
        self.output_weights = None
        self.dropout_dict = {}
        self.disable_cache = not CONFIG.USE_CACHE
        

        for col in self.configuration['input_features']:
            if len(self.configuration['input_features']) > 1:
                dropout = 0.0
            else:
                dropout = 0.0

            if 'dropout' in col:
                dropout = col['dropout']

            self.dropout_dict[col['name']] = dropout

        self._clear_cache()


    def _clear_cache(self):
        self.list_cache = {}
        self.encoded_cache = {}
        self.transformed_cache = None


    def extractRandomSubset(self, percentage):
        msk = np.random.rand(len(self.data_frame)) < (1-percentage)
        test_df = self.data_frame[~msk]
        self.data_frame = self.data_frame[msk]
        # clear caches
        self._clear_cache()

        ds = DataSource(test_df, self.configuration)
        ds.encoders = self.encoders
        ds.transformer = self.transformer
        return ds



    def __len__(self):
        """
        return the length of the datasource (as in number of rows)
        :return: number of rows
        """
        return int(self.data_frame.shape[0])

    def __getitem__(self, idx):
        """

        :param idx:
        :return:
        """
        sample = {}

        dropout_features = None

        if self.training == True and random.randint(0,2) == 1:
            dropout_features = [feature['name'] for feature in self.configuration['input_features'] if random.random() > (1 - self.dropout_dict[feature['name']])]


        if self.transformed_cache is None and not self.disable_cache:
            self.transformed_cache = [None] * self.__len__()

        if not self.disable_cache and not (dropout_features is not None and len(dropout_features) > 0):
            cached_sample = self.transformed_cache[idx]
            if cached_sample is not None:
                return cached_sample

        for feature_set in ['input_features', 'output_features']:
            sample[feature_set] = {}
            for feature in self.configuration[feature_set]:
                col_name = feature['name']
                col_config = self.get_column_config(col_name)
                if col_name not in self.encoded_cache: # if data is not encoded yet, encode values
                    if not ((dropout_features is not None and  col_name in dropout_features) or self.disable_cache):
                        self.get_encoded_column_data(col_name, feature_set)


                # if we are dropping this feature, get the encoded value of None
                if dropout_features is not None and col_name in dropout_features:
                    custom_data = {col_name:[None]}
                    # if the dropout feature depends on another column, also pass a None array as the dependant column
                    if 'depends_on_column' in col_config:
                        custom_data[custom_data['depends_on_column']]= [None]
                    sample[feature_set][col_name] = self.get_encoded_column_data(col_name, feature_set, custom_data=custom_data)[0]
                elif self.disable_cache:
                    sample[feature_set][col_name] = self.get_encoded_column_data(col_name, feature_set, custom_data={col_name: [self.data_frame[col_name].iloc[idx]]})[0]
                else:
                    sample[feature_set][col_name] = self.encoded_cache[col_name][idx]

        # Create weights if not already create
        if self.output_weights is None:
            for col_config in self.configuration['output_features']:
                if 'weights' in col_config:

                    weights = col_config['weights']
                    new_weights = None

                    for val in weights:
                        encoded_val = self.get_encoded_column_data(col_config['name'],'output_features',custom_data={col_config['name']:[val]})
                        value_index = np.argmax(encoded_val[0])

                        if new_weights is None:
                            new_weights = [0.2] * len(encoded_val[0])

                        new_weights[value_index] = weights[val]

                    if self.output_weights is None:
                        self.output_weights = new_weights
                    else:
                        self.output_weights.extend(new_weights)
                else:
                    self.output_weights = False

        if self.transformer:
            sample = self.transformer.transform(sample)

        if not self.disable_cache:
            self.transformed_cache[idx] = sample
            return self.transformed_cache[idx]
        else:
            return sample

    def get_column_original_data(self, column_name):
        """

        :param column_name:
        :return:
        """
        if self.disable_cache:
            return self.data_frame[column_name].tolist()

        if column_name in self.list_cache:
            return self.list_cache[column_name]

        if column_name in self.data_frame:
            self.list_cache[column_name] = self.data_frame[column_name].tolist()
            return self.list_cache[column_name]

        else:  # if column not in dataframe
            rows = self.data_frame.shape[0]
            return [None] * rows

    def get_encoded_column_data(self, column_name, feature_set = 'input_features', custom_data = None):
        """

        :param column_name:
        :return:
        """

        if column_name in self.encoded_cache and custom_data is None:
            return self.encoded_cache[column_name]

        # first argument of encoder is the data, so we either pass the custom data or we get the column data
        if custom_data is not None:
            args = [custom_data[column_name]]
        else:
            args = [self.get_column_original_data(column_name)]

        config = self.get_column_config(column_name)

        # see if the feature has dependencies in other columns
        if 'depends_on_column' in config:
            if custom_data is not None:
                arg2 = custom_data[config['depends_on_column']]
            else:
                arg2 = self.get_column_original_data(config['depends_on_column'])
            args += [arg2]

        if column_name in self.encoders:
            encoded_vals = self.encoders[column_name].encode(*args)
            if column_name not in self.encoded_cache and custom_data is None:
                self.encoded_cache[column_name] = encoded_vals
            return encoded_vals

        if 'encoder_class' not in config:
            path = 'lightwood.encoders.{type}'.format(type=config['type'])
            module = importlib.import_module(path)
            if hasattr(module, 'default'):
                encoder_class = importlib.import_module(path).default
            else:
                raise ValueError('No default encoder for {type}'.format(type=config['type']))
        else:
            encoder_class = config['encoder_class']

        encoder_attrs = config['encoder_attrs'] if 'encoder_attrs' in config else {}

        encoder_instance = encoder_class()

        for attr in encoder_attrs:
            if hasattr(encoder_instance, attr):
                setattr(encoder_instance, attr, encoder_attrs[attr])

        encoder_instance.prepare_encoder(args[0])
        self.encoders[column_name] = encoder_instance
        encoded_val = encoder_instance.encode(*args)

        if custom_data is None:
            self.encoded_cache[column_name] = encoded_val

        return encoded_val


    def get_decoded_column_data(self, column_name, encoded_data, decoder_instance=None):
        """
        :param column_name: column names to be decoded
        :param encoded_data: encoded data of tensor type
        :return decoded_data : Dict :Decoded data of input column
        """
        if decoder_instance is None:
            if column_name not in self.encoders:
                raise ValueError(
                    'Data must have been encoded before at some point, you should not decode before having encoding at least once')
            decoder_instance = self.encoders[column_name]
        decoded_data = decoder_instance.decode(encoded_data)

        return decoded_data

    def get_feature_names(self, where = 'input_features'):

        return [feature['name'] for feature in self.configuration[where]]

    def get_column_config(self, column_name):
        """
        Get the config info for the feature given a configuration as defined in data_schemas definition.py
        :param column_name:
        :return:
        """
        for feature_set in ['input_features', 'output_features']:
            for feature in self.configuration[feature_set]:
                if feature['name'] == column_name:
                    return feature


if __name__ == "__main__":
    import random
    import pandas

    config = {
        'name': 'test',
        'input_features': [
            {
                'name': 'x',
                'type': 'numeric',

            },
            {
                'name': 'y',
                'type': 'numeric',

            }
        ],

        'output_features': [
            {
                'name': 'z',
                'type': 'categorical',

            }
        ]
    }

    data = {'x': [i for i in range(10)], 'y': [random.randint(i, i + 20) for i in range(10)]}
    nums = [data['x'][i] * data['y'][i] for i in range(10)]

    data['z'] = ['low' if i < 50 else 'high' for i in nums]

    data_frame = pandas.DataFrame(data)

    print(data_frame)

    ds = DataSource(data_frame, config)

    print(ds.get_encoded_column_data('z'))
