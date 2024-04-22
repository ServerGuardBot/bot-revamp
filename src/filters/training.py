__author__ = "Baishali Dutta"
__copyright__ = "Copyright (C) 2022 Baishali Dutta"
__license__ = "Apache License 2.0"
__version__ = "0.1"

# -------------------------------------------------------------------------
#                           Import Libraries
# -------------------------------------------------------------------------

import pandas as pd
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.layers import Input, Dense, Dropout, \
    GlobalMaxPooling1D, LSTM, Bidirectional
from keras.models import Model

from .config import *
from filters.preprocessing import DataPreprocess


# -------------------------------------------------------------------------
#                   Build and Train the RNN Model Architecture
# -------------------------------------------------------------------------
def build_rnn_model(data, target_classes, embedding_layer):
    """
    Build and Train the RNN architecture (Bidirectional LSTM)
    :param data: the preprocessed padded data
    :param target_classes: Assigned target labels for the comments
    :param embedding_layer: Embedding layer comprising preprocessed comments
    :return: the trained model
    """
    # Create an LSTM Network with a single LSTM
    input_ = Input(shape=(MAX_SEQUENCE_LENGTH,))
    x = embedding_layer(input_)
    x = Bidirectional(LSTM(units=64,
                           return_sequences=True,
                           recurrent_dropout=0.2))(x)
    x = GlobalMaxPooling1D()(x)
    x = Dense(units=64, activation='relu')(x)
    x = Dropout(rate=0.2)(x)
    # x = GlobalMaxPooling1D()(x)

    #  Sigmoid Classifier
    output = Dense(len(DETECTION_CLASSES), activation="sigmoid")(x)

    model = Model(input_, output)

    # Display Model
    model.summary()

    # Compile Model
    model.compile(loss='binary_crossentropy',
                  optimizer='adam',
                  metrics=['accuracy'])

    # Define Callbacks
    # TODO Check whether to use the restore_best_weights
    early_stop = EarlyStopping(monitor='val_loss',
                               patience=5,
                               mode='min',
                               restore_best_weights=True)

    checkpoint = ModelCheckpoint(filepath=MODEL_LOC,  # saves the 'best' model
                                 monitor='val_loss',
                                 save_best_only=True,
                                 mode='min')

    # Fit Model
    history = model.fit(data,
                        target_classes,
                        batch_size=BATCH_SIZE,
                        epochs=EPOCHS,
                        validation_split=VALIDATION_SPLIT,
                        callbacks=[early_stop, checkpoint],
                        verbose=1,
                        use_multiprocessing=True)

    # Return Model Training History
    return model, history

def execute(data=TRAINING_DATA_LOC):
    """
    Import the training data csv file and save it into a dataframe
    :param data: the training data (CSV) location
    """
    training_data = pd.read_csv(data)

    preprocessing = DataPreprocess(training_data)
    build_rnn_model(preprocessing.padded_data,
                    preprocessing.target_classes,
                    preprocessing.embedding_layer)