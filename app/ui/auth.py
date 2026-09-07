import streamlit as st

def get_current_user_role() -> str:
    """Returns the current active user role from session_state, default to 'Procurement Officer'."""
    if "user_role" not in st.session_state:
        st.session_state["user_role"] = "Procurement Officer"
    return st.session_state["user_role"]

def get_current_username() -> str:
    if "username" not in st.session_state:
        st.session_state["username"] = "Officer Sharma"
    return st.session_state["username"]

def render_role_selector():
    """Renders a simple role switch dropdown in sidebar."""
    roles = ["Procurement Officer", "Admin", "Viewer"]
    current = get_current_user_role()
    idx = roles.index(current) if current in roles else 0

    selected = st.sidebar.selectbox(
        "Current Persona / Role",
        roles,
        index=idx,
        help="Switch roles to test permissions (Admin: settings/taxonomy; Procurement Officer: approve/reject; Viewer: read-only)"
    )

    if selected != current:
        st.session_state["user_role"] = selected
        if selected == "Admin":
            st.session_state["username"] = "Admin Officer"
        elif selected == "Procurement Officer":
            st.session_state["username"] = "Officer Sharma"
        else:
            st.session_state["username"] = "Guest Viewer"
        st.rerun()
