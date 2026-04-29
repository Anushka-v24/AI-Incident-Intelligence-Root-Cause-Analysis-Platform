from crewai import Agent, Task, Crew

class DebugCrew:
    def __init__(self, llm):
        self.llm = llm

    def run(self, events):

        events_text = "\n".join(events)

        # 🔍 Detection Agent
        detection_agent = Agent(
            role="Log Detection Expert",
            goal="Identify anomalies in system logs",
            backstory="Expert in analyzing distributed system logs",
            llm=self.llm
        )

        detection_task = Task(
            description=f"""
            The following log events were detected:

            {events_text}

            Identify what went wrong and summarize the anomaly.
            """,
            expected_output="A brief summary of the anomaly detected in the logs.",
            agent=detection_agent
        )

        # 🧠 Analysis Agent
        analysis_agent = Agent(
            role="Root Cause Analyst",
            goal="Find root cause of system issue",
            backstory="Expert in debugging system failures",
            llm=self.llm
        )

        analysis_task = Task(
            description="""
            Based on the previous analysis, explain the root cause clearly.
            """,
            expected_output="Detailed explanation of the root cause.",
            agent=analysis_agent
        )

        # 🛠 Fix Agent
        fix_agent = Agent(
            role="System Fix Advisor",
            goal="Suggest fixes and severity",
            backstory="Expert in solving system issues",
            llm=self.llm
        )

        fix_task = Task(
            description="""
            Provide:
            - Fix steps
            - Preventive measures
            - Severity level (LOW/MEDIUM/HIGH)
            """,
            expected_output="Fix steps, preventive measures, and severity level.",
            agent=fix_agent
        )

        # 🚀 Crew Execution
        crew = Crew(
            agents=[detection_agent, analysis_agent, fix_agent],
            tasks=[detection_task, analysis_task, fix_task],
            verbose=True
        )

        result = crew.kickoff()

        return result