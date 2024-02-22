__author__ = "Baishali Dutta"
__copyright__ = "Copyright (C) 2022 Baishali Dutta"
__license__ = "Apache License 2.0"
__version__ = "0.1"

import os

EMBEDDING_DIMENSION = 300
EMBEDDING_FILE_LOC = os.path.join(os.path.dirname(__file__), 'model/glove/glove.6B.' + str(EMBEDDING_DIMENSION) + 'd.txt')
TRAINING_DATA_LOC = os.path.join(os.path.dirname(__file__), 'data/train.csv')
MAX_VOCAB_SIZE = 20000
MAX_SEQUENCE_LENGTH = 100
BATCH_SIZE = 128
EPOCHS = 30
VALIDATION_SPLIT = 0.3
DETECTION_CLASSES = [
    'toxic',
    'severe_toxic',
    'obscene',
    'threat',
    'insult',
    'identity_hate',
    'neutral']
MODEL_LOC = os.path.join(os.path.dirname(__file__), 'model/comments_toxicity.h5')
TOKENIZER_LOC = os.path.join(os.path.dirname(__file__), 'model/tokenizer.pickle')