from app.core.logging import resolve_log_level
import logging


def test_resolve_log_level_explicit():
    assert resolve_log_level(log_level="WARNING", environment="local") == logging.WARNING
    assert resolve_log_level(log_level="debug", environment="production") == logging.DEBUG


def test_resolve_log_level_dev_default():
    assert resolve_log_level(environment="local", debug=False) == logging.DEBUG
    assert resolve_log_level(environment="production", debug=True) == logging.DEBUG


def test_resolve_log_level_prod_default():
    assert (
        resolve_log_level(log_level="", environment="production", debug=False)
        == logging.INFO
    )
