# Before running the sample:
#    pip install azure-ai-projects>=2.1.0

from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = "https://king-foundry-resource.services.ai.azure.com/api/projects/king-foundry"

project_client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
)

my_agent = "computing-historian"
my_version = "1"

openai_client = project_client.get_openai_client()

while True:
    user_input = input("You: ").strip()
    if user_input.lower() == "quit":
        break
    if not user_input:
        continue

    response = openai_client.responses.create(
        input=[{"role": "user", "content": user_input}],
        extra_body={"agent_reference": {"name": my_agent, "version": my_version, "type": "agent_reference"}},
    )

    print(f"Agent: {response.output_text}")



