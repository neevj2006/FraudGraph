import pytest

from ml.data.dataset import synthetic
from ml.pipeline import train


@pytest.fixture(scope="session")
def artifacts(tmp_path_factory):
    path = tmp_path_factory.mktemp("experiment")
    train(synthetic(900), path, "synthetic-test", epochs=8, seeds=(11,))
    return path
