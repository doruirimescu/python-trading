import logging

def get_debugging_logger(name: str = 'Debugging logger'):
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    DEBUGGING_LOGGER = logging.getLogger(name)
    DEBUGGING_LOGGER.setLevel(logging.DEBUG)
    DEBUGGING_LOGGER.propagate = True
    return DEBUGGING_LOGGER

def get_logger(name: str = 'Main logger'):
    FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(format=FORMAT)

    MAIN_LOGGER = logging.getLogger(name)
    MAIN_LOGGER.setLevel(logging.DEBUG)
    MAIN_LOGGER.propagate = True
    return MAIN_LOGGER
