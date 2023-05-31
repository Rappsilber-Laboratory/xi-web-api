class Config(object):
    DEBUG = False
    TESTING = False
    CORS_HEADERS = 'Content-Type'


class ProductionConfig(Config):
    ...


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
