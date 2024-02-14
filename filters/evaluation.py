__author__ = "Baishali Dutta"
__copyright__ = "Copyright (C) 2022 Baishali Dutta"
__license__ = "Apache License 2.0"
__version__ = "0.1"

# -------------------------------------------------------------------------
#                           Import Libraries
# -------------------------------------------------------------------------

import pickle
from keras.models import load_model
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences

from .config import *
from .cleaning import clean_text

def _load_model():
    try:
        return load_model(MODEL_LOC)
    except:
        return None

def predict(comment: str, rnn_model=None):
    """
    Makes prediction
    """
    with open(TOKENIZER_LOC, 'rb') as handle:
        tokenizer: Tokenizer = pickle.load(handle)
    
    if not rnn_model:
        rnn_model = load_model(MODEL_LOC)
    
    comment = clean_text(comment)
    
    sequences = tokenizer.texts_to_sequences([comment])
    padded_sequence = pad_sequences(sequences, maxlen=MAX_SEQUENCE_LENGTH)
    print(f'Sequence of "{comment}" is {padded_sequence}')

    prediction = rnn_model.predict(padded_sequence,
                                   steps=1,
                                   verbose=1)

    prediction = prediction[0]
    parsed = {}
    i = 0
    for label in DETECTION_CLASSES:
        parsed[label] = prediction[i]
        i += 1
    return parsed