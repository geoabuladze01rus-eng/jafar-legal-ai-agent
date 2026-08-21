from jafar.legal_entity_dossier import LegalEntityDossierBuilder
from jafar.legal_entity_intelligence import SourceFinding


def test_dossier_contains_auditable_source_findings():
    dossier = LegalEntityDossierBuilder().build(
        "ООО Ромашка",
        "name",
        [
            SourceFinding(
                source_key="kad",
                status="found",
                title="Арбитраж",
                details={"cases": 3},
                source_url="https://kad.arbitr.ru/",
            ),
            SourceFinding(
                source_key="fssp",
                status="no_data",
                title="ФССП",
                details={},
            ),
        ],
    )

    data = dossier.to_dict()
    assert data["query"] == "ООО Ромашка"
    assert len(data["sources"]) == 2
    assert data["sources"][1]["status"] == "no_data"
