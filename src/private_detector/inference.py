import tensorflow as tf

from absl import logging as absl_logging

from tensorflow import keras
from .preprocess import preprocess_for_evaluation
from os import path

def read_image(filename: str) -> tf.Tensor:
    """
    Load and preprocess image for inference with the Private Detector

    Parameters
    ----------
    filename : str
        Filename of image

    Returns
    -------
    image : tf.Tensor
        Image ready for inference
    """
    image = keras.preprocessing.image.load_img(filename, target_size=(480,480))
    image = keras.utils.img_to_array(image)
    image = tf.convert_to_tensor(image)
    # image = tf.io.read_file(filename)
    # image = tf.io.decode_jpeg(image, channels=3)

    image = preprocess_for_evaluation(
        image,
        480,
        tf.float16
    )

    image = tf.reshape(image, -1)

    return image

def load_model() -> tf.keras.Model:
    """
    Load Private Detector model

    Returns
    -------
    model : tf.keras.Model
        Private Detector model
    """
    tf.get_logger().setLevel('ERROR')
    absl_logging.set_verbosity(absl_logging.DEBUG)
    
    model = tf.saved_model.load(path.join(path.dirname(__file__), "saved_model"))

    return model