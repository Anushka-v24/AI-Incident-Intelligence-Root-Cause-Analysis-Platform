from crewai import Task

def create_tasks(detection_agent, analysis_agent, fix_agent, events):

    events_text = "\n".join(events)

    detection_task = Task(
        description=f"""
        These log events were detected:
        {events_text}

        Identify what went wrong and summarize the anomaly.
        """,
        agent=detection_agent
    )

    analysis_task = Task(
        description="""
        Based on previous analysis, identify root cause in detail.
        """,
        agent=analysis_agent
    )

    fix_task = Task(
        description="""
        Provide:
        - Fix steps
        - Preventive measures
        - Severity level
        """,
        agent=fix_agent
    )

    return detection_task, analysis_task, fix_task