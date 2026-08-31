from jafar import __version__
from jafar.main import app


def test_package_and_application_versions_share_one_source_of_truth():
    assert __version__ == "0.13.0"
    assert app.version == __version__
