from miniautogen.observability.logging import get_logger


def test_get_logger_returns_bound_logger() -> None:
    logger = get_logger("miniautogen.test")

    assert logger is not None
    assert hasattr(logger, "bind")
