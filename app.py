import streamlit as st
import pandas as pd
from datetime import date, timedelta

# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Smart Deadline Recovery Assistant",
    page_icon="🎓",
    layout="wide"
)

st.title("🎓 Smart Deadline Recovery Assistant")

st.write(
    "Missed a deadline? Recover your plan, not your progress. "
    "This assistant detects unfinished overdue tasks, reprioritizes "
    "remaining work, and suggests a recovery schedule for your approval."
)

st.info(
    "The assistant suggests when to work on tasks. "
    "It does not change your actual academic deadlines."
)


# =========================================================
# INITIALIZE TASK DATA
# =========================================================

if "tasks" not in st.session_state:
    st.session_state.tasks = pd.DataFrame([
        {
            "Task ID": 1,
            "Task": "AI Assignment",
            "Deadline": date.today() - timedelta(days=1),
            "Priority": "High",
            "Estimated Hours": 3.0,
            "Status": "Pending"
        },
        {
            "Task ID": 2,
            "Task": "DSA Practicum",
            "Deadline": date.today() + timedelta(days=1),
            "Priority": "High",
            "Estimated Hours": 2.0,
            "Status": "Pending"
        },
        {
            "Task ID": 3,
            "Task": "Data Science Project",
            "Deadline": date.today() + timedelta(days=3),
            "Priority": "Medium",
            "Estimated Hours": 4.0,
            "Status": "Pending"
        },
        {
            "Task ID": 4,
            "Task": "OS Revision",
            "Deadline": date.today() + timedelta(days=4),
            "Priority": "Medium",
            "Estimated Hours": 2.0,
            "Status": "Pending"
        },
        {
            "Task ID": 5,
            "Task": "IoT Notes",
            "Deadline": date.today() + timedelta(days=5),
            "Priority": "Low",
            "Estimated Hours": 1.0,
            "Status": "Pending"
        }
    ])

if "recovery_plan" not in st.session_state:
    st.session_state.recovery_plan = None

if "approved_plan" not in st.session_state:
    st.session_state.approved_plan = None


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def invalidate_old_plans():
    """Clear old proposals when the task list changes."""
    st.session_state.recovery_plan = None
    st.session_state.approved_plan = None


def get_overdue_tasks(tasks):
    """Find unfinished tasks whose actual deadline has passed."""
    today = date.today()

    return tasks[
        (tasks["Deadline"] < today) &
        (tasks["Status"] != "Completed")
    ].copy()


def get_active_tasks(tasks):
    """Return all tasks that are not completed."""
    return tasks[
        tasks["Status"] != "Completed"
    ].copy()


# =========================================================
# PRIORITY RECALCULATION
# =========================================================

def priority_score(row):
    """
    Transparent rule-based priority calculation.

    Higher score means the task should be considered earlier.
    """

    priority_values = {
        "High": 3,
        "Medium": 2,
        "Low": 1
    }

    today = date.today()
    days_left = (row["Deadline"] - today).days

    # Existing importance
    score = priority_values[row["Priority"]] * 3

    # Deadline urgency
    if days_left >= 0:
        score += max(0, 7 - days_left)

    # Additional urgency for overdue tasks
    else:
        overdue_days = abs(days_left)
        score += 12 + overdue_days

    # Additional urgency if student manually marked it Missed
    if row["Status"] == "Missed":
        score += 5

    return score


def priority_reason(row):
    """Explain why a task received its priority."""
    today = date.today()
    days_left = (row["Deadline"] - today).days

    reasons = []

    if row["Status"] == "Missed":
        reasons.append("Marked as missed")

    if days_left < 0:
        reasons.append(
            f"Overdue by {abs(days_left)} day(s)"
        )
    elif days_left == 0:
        reasons.append("Due today")
    elif days_left <= 2:
        reasons.append("Deadline approaching")

    reasons.append(f"{row['Priority']} original priority")

    return "; ".join(reasons)


def generate_recovery_plan(tasks, available_hours, planning_days):
    """
    Create a suggested schedule.

    Tasks are ordered by:
    1. Recalculated priority score
    2. Earliest actual deadline
    3. Shorter estimated effort

    Work is split across days when necessary.
    """

    active_tasks = get_active_tasks(tasks)

    if active_tasks.empty:
        return pd.DataFrame(), pd.DataFrame()

    active_tasks = active_tasks.copy()

    active_tasks["Recovery Score"] = active_tasks.apply(
        priority_score,
        axis=1
    )

    active_tasks["Reason"] = active_tasks.apply(
        priority_reason,
        axis=1
    )

    active_tasks = active_tasks.sort_values(
        by=["Recovery Score", "Deadline", "Estimated Hours"],
        ascending=[False, True, True]
    )

    schedule_rows = []
    unscheduled_rows = []

    current_day = date.today()

    # Remaining available work time for each day
    daily_remaining = available_hours

    for _, task in active_tasks.iterrows():

        hours_left = float(task["Estimated Hours"])

        while hours_left > 0.0001:

            # Move to the next day when today's capacity is full
            if daily_remaining <= 0.0001:
                current_day += timedelta(days=1)
                daily_remaining = available_hours

            # Stop when the planning window is over
            last_planning_day = (
                date.today() + timedelta(days=planning_days - 1)
            )

            if current_day > last_planning_day:
                break

            work_hours = min(
                hours_left,
                daily_remaining
            )

            schedule_rows.append({
                "Task": task["Task"],
                "Priority": task["Priority"],
                "Recovery Score": task["Recovery Score"],
                "Actual Deadline": task["Deadline"],
                "Suggested Work Date": current_day,
                "Work Hours": round(work_hours, 2),
                "Reason": task["Reason"]
            })

            hours_left -= work_hours
            daily_remaining -= work_hours

        # Record any work that could not fit in the planning window
        if hours_left > 0.0001:
            unscheduled_rows.append({
                "Task": task["Task"],
                "Remaining Hours": round(hours_left, 2),
                "Actual Deadline": task["Deadline"]
            })

    schedule_df = pd.DataFrame(schedule_rows)
    unscheduled_df = pd.DataFrame(unscheduled_rows)

    return schedule_df, unscheduled_df


# =========================================================
# SIDEBAR - ADD NEW TASK
# =========================================================

st.sidebar.header("➕ Add New Task")

with st.sidebar.form("add_task_form", clear_on_submit=True):

    task_name = st.text_input("Task Name")

    task_deadline = st.date_input(
        "Actual Deadline",
        value=date.today()
    )

    task_priority = st.selectbox(
        "Original Priority",
        ["High", "Medium", "Low"]
    )

    task_hours = st.number_input(
        "Estimated Hours",
        min_value=0.25,
        max_value=100.0,
        value=2.0,
        step=0.25
    )

    add_task_button = st.form_submit_button(
        "Add Task"
    )

if add_task_button:

    if task_name.strip():

        if st.session_state.tasks.empty:
            new_id = 1
        else:
            new_id = int(
                st.session_state.tasks["Task ID"].max()
            ) + 1

        new_task = pd.DataFrame([{
            "Task ID": new_id,
            "Task": task_name.strip(),
            "Deadline": task_deadline,
            "Priority": task_priority,
            "Estimated Hours": float(task_hours),
            "Status": "Pending"
        }])

        st.session_state.tasks = pd.concat(
            [st.session_state.tasks, new_task],
            ignore_index=True
        )

        invalidate_old_plans()

        st.sidebar.success("Task added successfully!")
        st.rerun()

    else:
        st.sidebar.error("Please enter a task name.")


# =========================================================
# CURRENT TASK PLAN
# =========================================================

st.header("📋 Current Task Plan")

tasks = st.session_state.tasks.copy()

if tasks.empty:
    st.info("No tasks added yet. Add your first task using the sidebar.")
else:
    st.dataframe(
        tasks.drop(columns=["Task ID"]),
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# AUTOMATIC OVERDUE DETECTION
# =========================================================

st.header("🚨 Missed Deadline Detection")

tasks = st.session_state.tasks.copy()

overdue_tasks = get_overdue_tasks(tasks)

if not overdue_tasks.empty:

    st.warning(
        f"{len(overdue_tasks)} unfinished task(s) have passed "
        "their actual deadline."
    )

    st.dataframe(
        overdue_tasks.drop(columns=["Task ID"]),
        use_container_width=True,
        hide_index=True
    )

else:
    st.success(
        "No overdue unfinished tasks detected right now."
    )


# =========================================================
# UPDATE TASK STATUS
# =========================================================

st.header("✅ Update Task Status")

if not tasks.empty:

    task_options = {
        f"{row['Task']} (ID: {row['Task ID']})": row["Task ID"]
        for _, row in tasks.iterrows()
    }

    selected_label = st.selectbox(
        "Select a task",
        list(task_options.keys())
    )

    selected_id = task_options[selected_label]

    selected_status = st.selectbox(
        "Choose status",
        ["Pending", "Missed", "Completed"]
    )

    if st.button("Update Status"):

        matching_rows = st.session_state.tasks[
            st.session_state.tasks["Task ID"] == selected_id
        ].index

        if len(matching_rows) > 0:

            st.session_state.tasks.loc[
                matching_rows[0], "Status"
            ] = selected_status

            invalidate_old_plans()

            st.success("Task status updated.")
            st.rerun()


# =========================================================
# RECOVERY SETTINGS
# =========================================================

st.divider()

st.header("🔄 Smart Recovery Planning")

st.write(
    "Tell the assistant how much time you can spend working each day. "
    "It will use this information to create a recovery proposal."
)

col1, col2 = st.columns(2)

with col1:
    available_hours = st.number_input(
        "Available work hours per day",
        min_value=0.5,
        max_value=16.0,
        value=3.0,
        step=0.5
    )

with col2:
    planning_days = st.number_input(
        "Plan for the next how many days?",
        min_value=1,
        max_value=30,
        value=7,
        step=1
    )


# =========================================================
# GENERATE RECOVERY PROPOSAL
# =========================================================

active_tasks = get_active_tasks(
    st.session_state.tasks
)

if active_tasks.empty:

    st.info(
        "There are no unfinished tasks to include in a recovery plan."
    )

else:

    if st.button(
        "🧠 Generate Smart Recovery Proposal",
        type="primary"
    ):

        schedule_df, unscheduled_df = generate_recovery_plan(
            st.session_state.tasks,
            available_hours,
            int(planning_days)
        )

        st.session_state.recovery_plan = {
            "schedule": schedule_df,
            "unscheduled": unscheduled_df,
            "available_hours": available_hours,
            "planning_days": int(planning_days)
        }

        st.session_state.approved_plan = None

        st.rerun()


# =========================================================
# DISPLAY RECOVERY PROPOSAL
# =========================================================

if st.session_state.recovery_plan is not None:

    proposal = st.session_state.recovery_plan

    recovery_table = proposal["schedule"]
    unscheduled_table = proposal["unscheduled"]

    st.divider()

    st.header("🧠 Suggested Recovery Schedule")

    st.caption(
        "This is a proposal generated using a transparent, "
        "rule-based priority calculation."
    )

    if not recovery_table.empty:

        st.dataframe(
            recovery_table,
            use_container_width=True,
            hide_index=True
        )

        st.subheader("📊 Daily Workload")

        daily_summary = (
            recovery_table
            .groupby("Suggested Work Date")["Work Hours"]
            .sum()
            .reset_index()
        )

        daily_summary.columns = [
            "Date",
            "Total Scheduled Hours"
        ]

        st.dataframe(
            daily_summary,
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No work could be scheduled.")

    # Show tasks that do not fit
    if not unscheduled_table.empty:

        st.warning(
            "Some work does not fit within the selected planning window. "
            "You may need more available time or a longer planning period."
        )

        st.dataframe(
            unscheduled_table,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.success(
            "All unfinished task hours fit within the proposed planning window."
        )

    # =====================================================
    # EXPLAIN PRIORITIZATION
    # =====================================================

    st.subheader("💡 Why were tasks prioritized this way?")

    st.write(
        "The assistant calculates a recovery score using:"
    )

    st.markdown("""
    - Original task priority
    - How close the actual deadline is
    - How many days overdue the task is
    - Whether the student marked the task as missed
    """)

    st.write(
        "Tasks with higher recovery scores are considered earlier. "
        "When a task needs more time than is available in one day, "
        "its work is split across multiple days."
    )

    st.warning(
        "The suggested work dates do not extend or change actual deadlines. "
        "Review the proposal carefully before approving it."
    )

    # =====================================================
    # HUMAN APPROVAL
    # =====================================================

    st.divider()

    st.header("👤 Student Approval")

    st.write(
        "The assistant does not apply the proposal automatically. "
        "You decide whether to accept it."
    )

    approve_col, reject_col = st.columns(2)

    with approve_col:

        if st.button(
            "✅ Approve Recovery Plan",
            type="primary"
        ):

            st.session_state.approved_plan = {
                "schedule": recovery_table.copy(),
                "unscheduled": unscheduled_table.copy(),
                "approved_on": date.today()
            }

            st.success(
                "Recovery proposal approved by the student!"
            )

            st.rerun()

    with reject_col:

        if st.button("❌ Reject Recovery Plan"):

            st.session_state.recovery_plan = None
            st.session_state.approved_plan = None

            st.warning(
                "Proposal rejected. Your original task list remains unchanged."
            )

            st.rerun()


# =========================================================
# APPROVED RECOVERY PLAN
# =========================================================

if st.session_state.approved_plan is not None:

    st.divider()

    st.header("📅 Student-Approved Recovery Plan")

    approved = st.session_state.approved_plan

    st.success(
        f"Your proposal was approved on {approved['approved_on']}."
    )

    st.dataframe(
        approved["schedule"],
        use_container_width=True,
        hide_index=True
    )

    if not approved["unscheduled"].empty:

        st.warning(
            "These hours still need to be planned:"
        )

        st.dataframe(
            approved["unscheduled"],
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Approval saves the proposed schedule in this app session. "
        "It does not mark tasks completed or change their actual deadlines."
    )


# =========================================================
# HOW THE ASSISTANT WORKS
# =========================================================

st.divider()

st.header("⚙️ How the Assistant Works")

st.markdown("""
### 1️⃣ Task Monitoring
The assistant stores tasks, actual deadlines, original priorities,
estimated effort, and completion status.

### 2️⃣ Automatic Missed Deadline Detection
It identifies unfinished tasks whose actual deadlines have passed.
Students can also manually mark a task as Missed.

### 3️⃣ Priority Recalculation
The assistant recalculates recovery priority using deadline urgency,
original priority, overdue duration, and task status.

### 4️⃣ Recovery Schedule
It proposes work dates based on the student's available hours per day.
Longer tasks can be split across multiple days.

### 5️⃣ Explanation
The assistant shows why tasks were prioritized and identifies work
that does not fit in the selected planning window.

### 6️⃣ Student Approval
The student can approve or reject the proposed recovery plan.
The assistant does not make the final decision automatically.

### 7️⃣ Updated Plan
After approval, the proposal is displayed as the student's
approved recovery plan. Actual academic deadlines remain unchanged.
""")

st.caption(
    "Smart Deadline Recovery Assistant — transparent, "
    "rule-based planning with student control."
)
# =========================================================
# DELETE TASK
# =========================================================

st.header("🗑️ Delete a Task")

if not st.session_state.tasks.empty:

    task_options = {
        f"{row['Task']} (ID: {row['Task ID']})": row["Task ID"]
        for _, row in st.session_state.tasks.iterrows()
    }

    selected_delete_label = st.selectbox(
        "Select the task you want to delete",
        list(task_options.keys()),
        key="delete_task_select"
    )

    selected_delete_id = task_options[selected_delete_label]

    if st.button("🗑️ Delete Selected Task"):

        st.session_state.tasks = st.session_state.tasks[
            st.session_state.tasks["Task ID"] != selected_delete_id
        ].reset_index(drop=True)

        invalidate_old_plans()

        st.success("Task deleted successfully!")
        st.rerun()

else:
    st.info("There are no tasks to delete.")