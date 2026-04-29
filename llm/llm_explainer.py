from crewai import LLM


def OllamaLLM(model="llama3"):
    model_name = model.removeprefix("ollama/")
    return LLM(
        model=f"ollama/{model_name}",
        base_url="http://localhost:11434",
    )
