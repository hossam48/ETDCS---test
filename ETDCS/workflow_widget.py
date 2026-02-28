# =============================================================================
# components/workflow_widget.py - Status Transition UI Component
# Task 8 - Phase 3
# =============================================================================
# Renders a status badge + transition button for a single entity.
# Used inside tasks_tab and mdl_tab.
# =============================================================================

import streamlit as st
from typing import Optional

from workflow_engine import (
    get_allowed_transitions,
    transition_deliverable,
    transition_task,
    get_audit_history,
    status_badge_html,
    TransitionResult,
)
from cache_manager import invalidate_project_cache


# =============================================================================
# MAIN WIDGET
# =============================================================================

def render_status_widget(
    entity_type: str,       # "deliverable" or "task"
    entity_id: int,
    current_status: str,
    entity_name: str,
    user_id: int,
    user_role: str,
    show_history: bool = False,
) -> Optional[str]:
    """
    Render a status badge with a transition dropdown + confirm button.

    Returns the new status string if a transition was made, else None.

    Args:
        entity_type:    "deliverable" or "task"
        entity_id:      DB row ID
        current_status: Current status string
        entity_name:    Display name (for confirmation message)
        user_id:        Current user's ID
        user_role:      Current user's role
        show_history:   Whether to show the audit trail expander
    """
    allowed = get_allowed_transitions(entity_type, current_status, user_role)

    col_badge, col_select, col_btn = st.columns([2, 2, 1])

    with col_badge:
        st.markdown(status_badge_html(current_status), unsafe_allow_html=True)

    with col_select:
        if allowed:
            new_status = st.selectbox(
                "Transition to",
                options=allowed,
                key=f"wf_select_{entity_type}_{entity_id}",
                label_visibility="collapsed",
            )
        else:
            st.caption("No transitions available")
            new_status = None

    with col_btn:
        if allowed and new_status:
            if st.button("Apply", key=f"wf_btn_{entity_type}_{entity_id}"):
                result = _do_transition(
                    entity_type, entity_id, new_status, user_id, user_role
                )
                if result.success:
                    invalidate_project_cache()
                    st.success(f"✅ {entity_name}: {result.message}")
                    st.rerun()
                else:
                    st.error(f"❌ {result.message}")
                return new_status if result.success else None

    # Optional audit trail
    if show_history:
        history = get_audit_history(entity_type, entity_id)
        if history:
            with st.expander(f"📋 History ({len(history)} changes)", expanded=False):
                for entry in history:
                    st.markdown(
                        f"**{entry['changed_at'][:16]}** — "
                        f"{status_badge_html(entry['from_status'])} → "
                        f"{status_badge_html(entry['to_status'])} "
                        f"<span style='color:#64748b'>by {entry['changed_by']}</span>",
                        unsafe_allow_html=True,
                    )

    return None


# =============================================================================
# COMPACT BADGE-ONLY VERSION (for dataframe rows)
# =============================================================================

def render_status_badge(status: str) -> None:
    """Render just a colored status badge (read-only)."""
    st.markdown(status_badge_html(status), unsafe_allow_html=True)


# =============================================================================
# BULK STATUS SECTION (for tasks_tab / mdl_tab list views)
# =============================================================================

def render_status_column(
    entity_type: str,
    rows: list,                 # list of dicts with id, name, status fields
    user_id: int,
    user_role: str,
    id_col: str = "id",
    name_col: str = "name",
    status_col: str = "status",
) -> None:
    """
    Render a status update section for a list of entities.

    Shows each entity's name, current status badge, and transition widget.
    Called from tasks_tab or mdl_tab to show a status management panel.

    Args:
        entity_type: "deliverable" or "task"
        rows:        List of dicts (id, name, status minimum)
        user_id:     Current user's ID
        user_role:   Current user's role
        id_col:      Column name for ID
        name_col:    Column name for display name
        status_col:  Column name for current status
    """
    if not rows:
        st.info("No items to display.")
        return

    for row in rows:
        entity_id = row.get(id_col)
        name = row.get(name_col, f"#{entity_id}")
        status = row.get(status_col, "")

        with st.container():
            st.markdown(f"**{name}**")
            render_status_widget(
                entity_type=entity_type,
                entity_id=entity_id,
                current_status=status,
                entity_name=name,
                user_id=user_id,
                user_role=user_role,
                show_history=True,
            )
            st.markdown("---")


# =============================================================================
# INTERNAL
# =============================================================================

def _do_transition(
    entity_type: str,
    entity_id: int,
    new_status: str,
    user_id: int,
    user_role: str,
) -> TransitionResult:
    """Dispatch to the correct engine function."""
    if entity_type == "deliverable":
        return transition_deliverable(entity_id, new_status, user_id, user_role)
    else:
        return transition_task(entity_id, new_status, user_id, user_role)
