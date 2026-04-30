import streamlit as st

from server.auth import create_user, verify_user


def render_auth_screen():
    left, right = st.columns([1.05, 0.95], vertical_alignment="center")
    with left:
        st.markdown(
            """
            <div class="auth-hero">
                <div class="eyebrow">Incident Operations Console</div>
                <h1>Detect failures before they become outages.</h1>
                <p>Analyze HDFS event streams, compare trained detectors, isolate likely triggers,
                and keep each operator's investigation history separate.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="auth-panel">', unsafe_allow_html=True)
        auth_tab, signup_tab = st.tabs(["Login", "Sign up"])
        with auth_tab:
            with st.form("login_form"):
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            if submitted:
                if verify_user(username, password):
                    st.session_state["user"] = username.strip().lower()
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
        with signup_tab:
            with st.form("signup_form"):
                username = st.text_input("Username", key="signup_username")
                password = st.text_input("Password", type="password", key="signup_password")
                confirm = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted:
                if password != confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, message, _ = create_user(username, password)
                    if ok:
                        st.session_state["user"] = username.strip().lower()
                        st.success("Account created. You are signed in.")
                        st.rerun()
                    else:
                        st.error(message)
        st.markdown("</div>", unsafe_allow_html=True)

