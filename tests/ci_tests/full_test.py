import os
import pandas as pd
from lightwood import Predictor
import lightwood

####################
config = {'input_features': [
                    {'name': 'number_of_bathrooms', 'type': 'numeric'}, {'name': 'sqft', 'type': 'numeric'},
                    {'name': 'location', 'type': 'categorical'}, {'name': 'days_on_market', 'type': 'numeric'},
                    {'name': 'neighborhood', 'type': 'categorical','dropout':0.4},{'name': 'rental_price', 'type': 'numeric'}],
 'output_features': [{'name': 'number_of_rooms', 'type': 'categorical', 'weights':{
    '0': 0.8,
    '1': 0.6,
    '2': 0.5,
    '3': 0.7,
    '4': 1,
 }}],
 'mixer':{'class': lightwood.BUILTIN_MIXERS.NnMixer}}

lightwood.config.config.CONFIG.USE_CUDA = False

df=pd.read_csv("https://mindsdb-example-data.s3.eu-west-2.amazonaws.com/home_rentals.csv")

predictor = Predictor(config)

def iter_function(epoch, error, test_error, test_error_gradient):
    print(
        'epoch: {iter}, error: {error}, test_error: {test_error}, test_error_gradient: {test_error_gradient}, accuracy: {accuracy}'.format(
            iter=epoch, error=error, test_error=test_error, test_error_gradient=test_error_gradient,
            accuracy=predictor.train_accuracy))


predictor.learn(from_data=df, callback_on_iter=iter_function, eval_every_x_epochs=2, stop_training_in_x_seconds=30)

print(predictor.predict(when={'number_of_rooms':3, 'number_of_bathrooms':2, 'sqft':700, 'location':'great'}))
