import pytest

from jafar.ai_network_policy import AIMode, AINetworkPolicy, DataClassification


def test_default_is_synthetic_only():
    with pytest.raises(PermissionError): AINetworkPolicy().authorize(provider_enabled=True, credential="x", data=DataClassification.SYNTHETIC)


def test_private_data_and_missing_credential_are_blocked():
    policy = AINetworkPolicy(mode=AIMode.LOCAL_LIVE_TEST, allow_live_network=True)
    with pytest.raises(PermissionError): policy.authorize(provider_enabled=True, credential="x", data=DataClassification.PRIVATE_CLIENT)
    with pytest.raises(PermissionError): policy.authorize(provider_enabled=True, credential=None, data=DataClassification.SYNTHETIC)
