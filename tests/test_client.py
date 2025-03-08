from unittest.mock import patch
import json
import os
from client import AppState, process_message
from datatypes import Conversation
from scenario import Scenario


def _load_scenarios(scenario_dir):
    scenarios = []
    for filename in os.listdir(scenario_dir):
        if filename.endswith('.json'):
            with open(os.path.join(scenario_dir, filename), 'r') as file:
                scenario_data = json.load(file)
                scenario = Scenario(**scenario_data)
                scenarios.append(scenario)
    return scenarios


def test_process_message():
    scenario_dir = 'tests/scenarios'
    scenarios: list[Scenario] = _load_scenarios(scenario_dir)
    
    for scenario in scenarios:
        state = AppState(calender_conversations=scenario.initial_state)
        message = scenario.new_message
        
        
        updated_state = process_message(state, message)
        
        _compare_conversations(updated_state.calender_conversations, scenario.expected_state, ["last_updated"])



def _compare_conversations(conversations: list[Conversation], expected_conversations: list[Conversation], excluded: list[str]):
    for conversation, expected_conversation  in zip(conversations, expected_conversations):
        assert conversation.model_dump(exclude=excluded) == expected_conversation.model_dump(exclude=excluded)