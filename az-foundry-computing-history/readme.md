https://microsoftlearning.github.io/mslearn-agent-quickstart/?azure-portal=true

Install the Azure AI projects and OpenAI SDKs by running the following command:
pip install azure-ai-projects>=2.1.0 openai

After the libraries are installed (which may take a minute or so), use the following command to sign into Azure.
az login

After you have signed in, enter the following command to run the application:
python agent.py

Some suggested prompts to try:
Tell me about the Commodore 64
What was the ZX Spectrum?
What was Grace Hopper's contribution to computing?
When you’re finished, enter quit.



(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& ..\computing-history\.venv\Scripts\Activate.ps1)