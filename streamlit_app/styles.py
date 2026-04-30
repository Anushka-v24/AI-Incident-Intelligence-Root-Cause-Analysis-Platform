APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --bg: #f4f7fb;
    --panel: #ffffff;
    --panel-soft: #eef3f8;
    --ink: #17212b;
    --muted: #647284;
    --line: #d8e0ea;
    --accent: #0e7c86;
    --accent-strong: #095f67;
    --danger: #b42318;
    --success: #067647;
}

.stApp {
    background:
        linear-gradient(180deg, rgba(14, 124, 134, 0.08), rgba(244, 247, 251, 0) 340px),
        var(--bg);
    color: var(--ink);
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

[data-testid="stHeader"] {
    background: rgba(244, 247, 251, 0.86);
    backdrop-filter: blur(10px);
}

[data-testid="stSidebar"] {
    background: #0f1d2b;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

[data-testid="stSidebar"] * {
    color: #f7fafc;
}

[data-testid="stSidebar"] [data-baseweb="select"] *,
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {
    color: #17212b !important;
}

.block-container {
    max-width: 1280px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}

h1 {
    color: #111827;
    font-weight: 800;
    letter-spacing: 0;
}

h2, h3 {
    color: #17212b;
    font-weight: 750;
    letter-spacing: 0;
}

.hero-strip {
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 22px 24px;
    background: linear-gradient(135deg, #ffffff 0%, #eef8f8 62%, #f7fafc 100%);
    box-shadow: 0 14px 36px rgba(18, 38, 63, 0.08);
    margin-bottom: 20px;
}

.hero-strip .eyebrow,
.auth-hero .eyebrow {
    color: var(--accent-strong);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 800;
    margin-bottom: 8px;
}

.hero-strip p,
.auth-hero p {
    color: var(--muted);
    max-width: 760px;
    margin-bottom: 0;
}

.section-title {
    color: #17212b;
    font-size: 1.18rem;
    font-weight: 750;
    margin: 20px 0 10px;
}

[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 14px 16px;
    box-shadow: 0 10px 28px rgba(18, 38, 63, 0.06);
}

div[data-testid="stTabs"] button {
    font-weight: 650;
}

.stDataFrame {
    border: 1px solid var(--line);
    border-radius: 8px;
    overflow: hidden;
    background: var(--panel);
}

.auth-hero {
    padding: 38px 8px;
}

.auth-hero h1 {
    font-size: clamp(2.1rem, 4vw, 4.2rem);
    line-height: 1.02;
    max-width: 760px;
    margin-bottom: 18px;
}

.auth-panel {
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 22px;
    box-shadow: 0 22px 60px rgba(18, 38, 63, 0.13);
}

.stButton > button,
.stDownloadButton > button,
button[kind="primary"] {
    border-radius: 8px;
    font-weight: 700;
}

.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
button[kind="primary"] {
    background: var(--accent);
    border-color: var(--accent);
}

.stRadio [role="radiogroup"] {
    gap: 10px;
}
</style>
"""

