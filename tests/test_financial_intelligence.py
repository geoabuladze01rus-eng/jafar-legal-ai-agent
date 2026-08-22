from jafar.financial_intelligence import FinancialIntelligence, FinancialPeriod


def test_financial_intelligence_detects_material_signals():
    result = FinancialIntelligence().analyze([
        FinancialPeriod(2024, revenue=100, profit=10, assets=100, liabilities=40),
        FinancialPeriod(2025, revenue=60, profit=-5, assets=100, liabilities=90),
    ])
    types = {signal["type"] for signal in result["signals"]}
    assert {"revenue_decline", "loss", "high_liability_ratio"} <= types
