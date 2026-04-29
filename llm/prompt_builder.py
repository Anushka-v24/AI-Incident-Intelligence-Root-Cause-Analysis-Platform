# llm/prompt_builder.py

class PromptBuilder:
    def __init__(self):
        pass

    def build_prompt(self, event_descriptions):
        events_text = "\n".join([f"- {e}" for e in event_descriptions])

        prompt = f"""
You are an expert system debugging assistant.

The system has detected an anomaly in log sequences.

The following log events were identified as important:
{events_text}

Your task:
1. Explain what went wrong in simple terms.
2. Identify possible root causes.
3. Suggest how to fix the issue.
4. Mention if this is critical or not.

Keep the explanation clear and concise.
"""

        return prompt.strip()