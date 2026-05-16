from __future__ import annotations

from medidiet.engine import RecommendationEngine
from medidiet.fixtures import DEMO_NOW, demo_request
from medidiet.rules import load_baseline_rule_pack


def main() -> None:
    patient, intake_records, menu_items, meal_label = demo_request()
    result = RecommendationEngine(load_baseline_rule_pack(), now=DEMO_NOW).recommend(
        patient,
        intake_records,
        menu_items,
        meal_label,
    )
    print(result.trace.to_json())


if __name__ == "__main__":
    main()
