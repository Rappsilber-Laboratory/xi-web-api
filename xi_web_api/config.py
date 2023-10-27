class Config(object):
    DEBUG = False
    TESTING = False
    CORS_HEADERS = 'Content-Type'


class ProductionConfig(Config):
    DEBUG = True


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
