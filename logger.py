import logging


def get_logger(log_file_path):
    logger = logging.getLogger("sandbox_reporting_logger")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s:%(filename)s:%(lineno)d %(message)s')

    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


if __name__ == "__main__":
    logger = get_logger("fsd", "lol")
    logger.info("yo")
