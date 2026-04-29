import pandas as pd
import re


class EventMapper:
    def __init__(self, filepath):
        self.filepath = filepath
        self.templates = self._load_templates(filepath)

    def _load_templates(self, filepath):
        try:
            df = pd.read_csv(filepath)
        except FileNotFoundError:
            return {}

        if {"EventId", "EventTemplate"}.issubset(df.columns):
            return dict(zip(df["EventId"], df["EventTemplate"]))
        return {}

    def map_events(self, events):
        mapped = []
        for event_id in events:
            template = self.get_template(event_id)
            mapped.append(f"{event_id}: {template}")
        return mapped

    def get_template(self, event_id):
        template = self.templates.get(event_id, "Unknown event template")
        template = re.sub(r"\[\*\]|<\*>|<var>", " ", str(template))
        template = re.sub(r"\s+([:,.])", r"\1", template)
        template = re.sub(r"\s+", " ", template)
        return template.strip()

    def summarize_events(self, events):
        rows = []
        seen = {}
        for event_id in events:
            seen[event_id] = seen.get(event_id, 0) + 1

        for event_id, count in seen.items():
            rows.append(
                {
                    "Event ID": event_id,
                    "Count": count,
                    "Template": self.get_template(event_id),
                }
            )
        return rows
