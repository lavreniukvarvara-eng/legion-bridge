import os
import json
import logging
from datetime import datetime

# Глушим внутренние варнинги Streamlit в логах
logging.getLogger("streamlit.runtime.scriptrunner.script_run_context").setLevel(logging.ERROR)
logging.getLogger("streamlit").setLevel(logging.ERROR)

import streamlit as st
from google import genai

DB_FILE = "tickets_db.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    if "GEMINI_API_KEY" not in os.environ:
        st.error("Please set the GEMINI_API_KEY environment variable.")
        st.stop()

    client = genai.Client()

    st.set_page_config(page_title="Legion Health: Bridge & Tracker", page_icon="⚡", layout="wide")
    st.title("⚡ Operations-to-Engineering Bridge & Tracker")
    st.caption("Vibecoding Sandbox: Form-agnostic internal system for automated PRD handling, tracking, and communication.")

    db = load_db()

    tab1, tab2, tab3 = st.tabs(["👋 Non-Tech Staff Intake", "🛠️ Developer Workspace", "📊 Ticket Tracker Dashboard"])

    with tab1:
        st.subheader("Submit your operational pain point, idea, or bug description")
        st.info("No formatting rules. Explain it exactly as you see it. An AI-agent will process it for the engineering team.")
        
        with st.form("staff_intake_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Your Full Name:", placeholder="e.g., Sarah Jenkins")
                email = st.text_input("Your Email Address:", placeholder="sjenkins@legionhealth.com")
            with col2:
                team = st.selectbox("Your Department / Team:", ["Clinical Ops", "Growth/GTM", "Finance", "Legal/Compliance", "Other"])
            
            raw_request = st.text_area(
                "Describe what is broken, what's slow, or what you need automated:",
                placeholder="Every Friday I manually pull up clinical schedules to match them with...",
                height=150
            )
            
            submitted = st.form_submit_button("Submit Request to Engineering 🚀")
            
            if submitted:
                if not name or not email or not raw_request:
                    st.error("Please fill out your Name, Email, and Request description.")
                else:
                    ticket_id = f"LEGION-{int(datetime.now().timestamp())}"
                    
                    ai_analysis_prompt = f"""
                    You are an AI Product Operations Lead at Legion Health. A non-technical team member ({name} from {team}) submitted this request:
                    "{raw_request}"

                    Perform 3 strict operations and output the result in a clean, parsable JSON structure using these exact keys:
                    1. "tech_specs": Translate the request into a precise, concise bulleted technical specification for software developers.
                    2. "priority": Assess severity/impact. Return exactly one value: "High", "Medium", or "Low".
                    3. "completeness_check": Analyze if engineers have enough info to act. Return either "Complete" or "Needs Clarification".
                    4. "missing_details_prompt": If "Needs Clarification", write a direct, polite question asking the user for the exact missing metric, step, or access requirement. If "Complete", write "None".

                    Respond ONLY with a valid JSON object. Do not include markdown code fences like ```json.
                    """
                    
                    with st.spinner("AI-agent analyzing request logic, urgency, and scoping details..."):
                        try:
                            response = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=ai_analysis_prompt
                            )
                            clean_text = response.text.strip().replace("```json", "").replace("```", "")
                            ai_data = json.loads(clean_text)
                        except Exception as e:
                            ai_data = {
                                "tech_specs": f"Review required: {raw_request}",
                                "priority": "Medium",
                                "completeness_check": "Needs Clarification",
                                "missing_details_prompt": "Could you please provide a step-by-step example of this issue?"
                            }

                    db[ticket_id] = {
                        "metadata": {
                            "submitted_by": name,
                            "email": email,
                            "team": team,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                        },
                        "raw_content": raw_request,
                        "ai_analysis": ai_data,
                        "status": "Backlog",
                        "dev_questions": [],
                        "staff_replies": []
                    }
                    save_db(db)
                    st.success(f"Successfully filed! Logged under Ticket ID: {ticket_id}.")

    with tab2:
        st.subheader("Engineering Backlog & Requirement Control Panel")
        if not db:
            st.write("No active tasks found in the database.")
        else:
            selected_id = st.selectbox("Select Active Ticket to Review:", list(db.keys()))
            t_data = db[selected_id]
            st.divider()
            
            col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
            col_meta1.metric("Origin Source", f"{t_data['metadata']['submitted_by']} ({t_data['metadata']['team']})")
            col_meta2.metric("System Urgency", t_data['ai_analysis']['priority'])
            col_meta3.metric("Completeness Rating", t_data['ai_analysis']['completeness_check'])
            
            current_status = t_data.get("status", "Backlog")
            status_options = ["Backlog", "In Progress", "Done"]
            new_status = col_meta4.selectbox("Modify Implementation Status:", status_options, index=status_options.index(current_status))
            if new_status != current_status:
                db[selected_id]["status"] = new_status
                save_db(db)
                st.rerun()

            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown("### 📥 Original Input (Messy Format)")
                st.code(t_data['raw_content'], language="text")
                if t_data['ai_analysis']['completeness_check'] == "Needs Clarification":
                    st.warning(f"⚠️ **Automated System Message Sent to {t_data['metadata']['email']}:**\n{t_data['ai_analysis']['missing_details_prompt']}")

            with col_right:
                st.markdown("### 🤖 Compiled AI Engineering Specifications")
                st.markdown(t_data['ai_analysis']['tech_specs'])

            st.divider()
            st.markdown("### 💬 Communication Loops & Clarifications")
            
            if t_data.get("dev_questions"):
                st.markdown("**Previous Threads:**")
                for idx, q in enumerate(t_data["dev_questions"]):
                    st.markdown(f"**Dev Question [{idx+1}]:** {q}")
                    if idx < len(t_data.get("staff_replies", [])):
                        st.markdown(f"*↳ Staff Answer:* {t_data['staff_replies'][idx]}")
                    else:
                        st.caption("*Waiting for staff reply...*")

            with st.form("ask_staff_form"):
                dev_q = st.text_input(f"Is something unclear? Input a question to push back to {t_data['metadata']['submitted_by']}:")
                send_q = st.form_submit_button("Send Question to Staff ✉️")
                if send_q and dev_q:
                    db[selected_id]["dev_questions"].append(dev_q)
                    db[selected_id]["ai_analysis"]["completeness_check"] = "Needs Clarification"
                    
                    mock_reply = f"Automated Mock Reply: Here are the extra parameters for '{dev_q[:15]}...' — everything is cleared now."
                    db[selected_id]["staff_replies"].append(mock_reply)
                    db[selected_id]["ai_analysis"]["completeness_check"] = "Complete"
                    
                    save_db(db)
                    st.success("Message dispatched!")
                    st.rerun()

    with tab3:
        st.subheader("Global Project Velocity Tracker")
        if not db:
            st.info("No active tickets to track.")
        else:
            table_rows = []
            for tid, data in db.items():
                table_rows.append({
                    "Ticket ID": tid,
                    "Date Logged": data["metadata"]["timestamp"],
                    "Staff Member": data["metadata"]["submitted_by"],
                    "Team Area": data["metadata"]["team"],
                    "Urgency": data["ai_analysis"]["priority"],
                    "Spec Readiness": data["ai_analysis"]["completeness_check"],
                    "Current Workflow Status": data.get("status", "Backlog")
                })
            
            st.dataframe(table_rows, use_container_width=True, hide_index=True)
            
            backlog_cnt = sum(1 for r in table_rows if r["Current Workflow Status"] == "Backlog")
            prog_cnt = sum(1 for r in table_rows if r["Current Workflow Status"] == "In Progress")
            done_cnt = sum(1 for r in table_rows if r["Current Workflow Status"] == "Done")
            
            st.divider()
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            metric_col1.metric("Items in Backlog", backlog_cnt)
            metric_col2.metric("Actively In Progress", prog_cnt)
            metric_col3.metric("Shipped/Done ✅", done_cnt)
