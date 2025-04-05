import pytest
from unittest.mock import patch
import json
import os
from client import AppState, process_message
from datatypes import Message
from scenario import Scenario


def load_scenarios(scenario_dir: str) -> list[tuple[str, Scenario]]:
    scenarios = []
    for filename in os.listdir(scenario_dir):
        if filename.endswith('.json'):
            with open(os.path.join(scenario_dir, filename), 'r') as file:
                data = json.load(file)
                scenario = Scenario(**data)
                scenarios.append((filename, scenario))
    return scenarios


@pytest.mark.parametrize("scenario_name, scenario", load_scenarios('tests/scenarios'))
def test_process_message(scenario_name: str, scenario: Scenario):
    state = AppState(calender_conversations=scenario.initial_state)
    
    # Extract message details
    classified_message = scenario.new_message
    message_data = classified_message.model_dump(exclude="classification")
    message = Message(**message_data)
    
    with patch("client.is_calendar_event") as mock_is_cal:
        mock_is_cal.return_value = classified_message 
        updated_state = process_message(state, message)
        
    # Enhanced comparison with scenario context
    try:
        _compare_conversations(
            convs=updated_state.calender_conversations,
            expected=scenario.expected_state,
            excluded=["last_updated"],
            scenario_name=scenario_name
        )
    except AssertionError as e:
        pytest.fail(f"Scenario '{scenario_name}' failed: {str(e)}")


def _compare_conversations(convs, expected, excluded, scenario_name):
    assert len(convs) == len(expected), (
        f"{scenario_name}: Expected {len(expected)} conversations but got {len(convs)}"
    )
    
    for conv, exp in zip(convs, expected):
        actual = conv.model_dump(exclude=excluded)
        expected_data = exp.model_dump(exclude=excluded)
        
        assert actual == expected_data, (
            f"{scenario_name}: Mismatch\n"
            f"Actual: {actual}\nExpected: {expected_data}"
        )
