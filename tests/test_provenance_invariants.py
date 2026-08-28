import pytest

from jafar.legal_position_service import validate_provenance


def test_same_matter_provenance_passes(): validate_provenance(matter_id="a", document_matter_id="a")
def test_cross_matter_provenance_rejected():
    with pytest.raises(ValueError, match="does not belong"): validate_provenance(matter_id="a", document_matter_id="b")
def test_missing_document_rejected():
    with pytest.raises(ValueError, match="missing"): validate_provenance(matter_id="a", document_matter_id=None, document_exists=False)
