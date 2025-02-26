import argparse
from pathlib import Path
from ollama import chat
from pydantic import BaseModel
from itertools import product


class ChatMessage(BaseModel):
    user: str
    message: str


class MessageStream(BaseModel):
    messages: list[ChatMessage]


def generate_chat(purpose, intent, model="qwen2.5-coder:32b", retries_left=3):
    prompt = f"""
    I need your help to generate dummpy data for a demo.
    create a sequence of messages similar to a chat in an IRC channel with multiple users where,

    the user wants to {intent} with the purpose of {purpose}.
    
    
    1. pick the number of users and their usernames in the conversation
    2. generate replies with other users participating to help in response to continue the chat for 3-4 messages or more
     
    Example of what an IIRC conversation might look like: 

    hstefan 	hey e_t_, been wrestling with some virtualbox resolution issues
    e_t_ 	hstefan: yeah? want to jump on a call and troubleshoot together?
    flavio 	I could join if you’re doing a screen share debugging session
    hstefan 	that sounds great - google meet or discord?
    e_t_ 	discord works for me. how about this evening around 8?
    flavio 	+1 for discord, 8pm UTC?
    hstefan 	works for me. I’ll send the invite link
    e_t_ 	cool, see you all then

    DO NOT use the same conversation as the example, we need variety.
    """
    if retries_left == 0:
        raise ValueError("Failed to generate chat after retries")
    response = chat(
        messages=[
            {"role": "user", "content": prompt},
        ],
        model=model,
        format=MessageStream.model_json_schema(),
    )
    try:
        return MessageStream.model_validate_json(response.message.content)
    except Exception as e:
        print(f"Error generating response: {e}, for purpose: {purpose}")
        return generate_chat(prompt, retries_left - 1)


def generate_synthetic_data(purposes: list[str], intents: list[str], n: int):
    for intent, purpose in product(intents, purposes):
        for _ in range(n):
            yield generate_chat(purpose=purpose, intent=intent, model="deepseek-r1:32b")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic chat data.")
    parser.add_argument("output_folder", type=str, help="The folder where the output JSON files will be saved.")
    
    args = parser.parse_args()
    output_path = Path(args.output_folder)
    output_path.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists

    intents = [
        "get someone on a quick call to help out",
        "plan a meeting",
        "reschedule an existing meeting",
    ]

    purposes = [
        "brainstorm a system design",
        "brainstorm on an issue you are stuck on",
        "facing issues with parts of the codebase that the team member has more context on",
        "brain scratching technical issues like database migration gone bad or unknown merge conflicts",
        "production hot fixes",
        "sprint plannng discussion",
        "feedback discussions (one-on-one)",
        "roadmap plannning",
        "feedback on a presentation",
        "how to showcase particular edge cases being handled for an update to the client",
        "dry run of demos to showcase to the client",
        "team lead proposes a meeting after a client call to discuss next steps",
    ]

    generator = generate_synthetic_data(intents, purposes, n=10)
    index = 0
    for message_stream in generator:
        file_path = f"{output_path}/chat_{index}.json"
        with open(file_path, "w") as file:
            file.write(message_stream.model_dump_json())
        index += 1