import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

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

def send_email_notification(recipient_email, recipient_name, ticket_id, question_text):
    smtp_server = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(st.secrets.get("SMTP_PORT", 587))
    smtp_user = st.secrets.get("SMTP_USER", "")
    smtp_password = st.secrets.get("SMTP_PASSWORD", "")
    
    if not smtp_user or not smtp_password:
        st.warning(f"⚠️ Email configured for {recipient_email}, but SMTP secrets are missing.")
        return False

    msg_body = f"""Hi {recipient_name},

Our Engineering team needs a quick clarification regarding your request ({ticket_id}):

"{question_text}"

Please reply directly to this email or update it in the tracking dashboard.

Best regards,
Legion Health Engineering Team
"""
    try:
        msg = MIMEText(msg_body)
        msg['Subject'] = f"[Legion Engineering] Action Required for {ticket_id}"
        msg['From'] = smtp_user
        msg['To'] = recipient_email

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

if __name__ == "__main__":
    if "GEMINI_API_KEY" not in os.environ:
        st.error("Please set the GEMINI_API_KEY environment variable.")
        st.stop()

    client = genai.Client()

    st.set_page_config(page_title="Legion Health: Bridge & Tracker", page_icon="⚡", layout="wide")
    st.title("⚡ Operations-to-Engineering Bridge & Tracker")
    st.caption("Legion Health Internal Tools Automation Sandbox")

    db = load_db()

    tab1, tab2, tab3 = st.tabs(["👋 Non-Tech Staff Intake", "🛠️ Developer Workspace", "📊 Ticket Tracker Dashboard"])

    # ==========================================
    # TAB 1: INTAKE FORM
    # ==========================================
    with tab1:
        st.subheader("Submit Operational Issue / Automation Request")
        
        with st.form("staff_intake_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Your Name:", placeholder="e.g., Sarah Jenkins")
                email = st.text_input("Your Email:", placeholder="sjenkins@legionhealth.com")
            with col2:
                team = st.selectbox("Department:", ["Clinical Ops", "Growth/GTM", "Finance", "Legal", "Other"])
            
            raw_request = st.text_area("What needs fixing or automating?", height=120)
            submitted = st.form_submit_button("Submit to Engineering 🚀")
            
            if submitted:
                if not name or not email or not raw_request:
                    st.error("Please fill out all fields.")
                else:
                    ticket_id = f"LEGION-{int(datetime.now().timestamp())}"
                    
                    # Промпт жестко оптимизирован под супер-короткий и емкий формат ТЗ
                    ai_analysis_prompt = f"""
                    You are a Technical Product Manager at Legion Health. Strip all fluff from this operational request:
                    "{raw_request}"

                    Convert it into an ultra-concise, high-density JSON. Keep descriptions minimal and actionable.
                    
                    Expected JSON format:
                    {{
                      "tech_specs": "### 🎯 Objective\\n[1 concise sentence explaining what to build]\\n\\n### 👤 User Story\\n**As a** {team} staff member, **I want** [core feature] **so that** [value].\\n\\n### 🛠️ Technical Tasks & Scope\\n- **Task 1:** [Actionable dev task]\\n- **Task 2:** [Actionable dev task]\\n- **Acceptance Criteria:** [Explicit definition of done]",
                      "priority": "High/Medium/Low",
                      "completeness_check": "Complete/Needs Clarification",
                      "missing_details_prompt": "[Polite 1-sentence question if information is missing, otherwise 'None']"
                    }}

                    Respond ONLY with the raw JSON object. No markdown code fences.
                    """
                    
                    with st.spinner("Compiling technical requirements..."):
                        try:
                            response = client.models.generate_content(
                                model='gemini-2.5-flash',
                                contents=ai_analysis_prompt
                            )
                            clean_text = response.text.strip().replace("```json", "").replace("```", "")
                            ai_data = json.loads(clean_text)
                        except Exception:
                            ai_data = {
                                "tech_specs": f"### 🎯 Objective\nReview raw ops request.\n\n### 🛠️ Scope\n- **Fix:** {raw_request[:50]}...",
                                "priority": "Medium",
                                "completeness_check": "Needs Clarification",
                                "missing_details_prompt": "Could you provide more context on the current workflow?"
                            }

                    db[ticket_id] = {
                        "metadata": {"submitted_by": name, "email": email, "team": team, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")},
                        "raw_content": raw_request,
                        "ai_analysis": ai_data,
                        "status": "Backlog",
                        "dev_questions": [],
                        "staff_replies": []
                    }
                    save_db(db)
                    st.success(f"Logged under Ticket ID: {ticket_id}.")

    # ==========================================
    # TAB 2: DEVELOPER WORKSPACE
    # ==========================================
    with tab2:
        st.subheader("Engineering Requirements Control Panel")
        if not db:
            st.write("No active tasks.")
        else:
            selected_id = st.selectbox("Select Ticket:", list(db.keys()))
            t_data = db[selected_id]
            st.divider()
            
            col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
            col_meta1.metric("Source", f"{t_data['metadata']['submitted_by']} ({t_data['metadata']['team']})")
            col_meta2.metric("Priority", t_data['ai_analysis']['priority'])
            col_meta3.metric("Status Check", t_data['ai_analysis']['completeness_check'])
            
            current_status = t_data.get("status", "Backlog")
            status_options = ["Backlog", "In Progress", "Done"]
            new_status = col_meta4.selectbox("Workflow Status:", status_options, index=status_options.index(current_status))
            if new_status != current_status:
                db[selected_id]["status"] = new_status
                save_db(db)
                st.rerun()

            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown("### 📥 Raw Operational Input")
                st.info(t_data['raw_content'])
                if t_data['ai_analysis']['completeness_check'] == "Needs Clarification":
                    st.warning(f"⚠️ **Pending Question to User:** {t_data['ai_analysis']['missing_details_prompt']}")

            with col_right:
                st.markdown("### 🤖 Concise Technical Specs")
                st.markdown(t_data['ai_analysis']['tech_specs'])

            st.divider()
            st.markdown("### 💬 Clarification Loops")
            
            if t_data.get("dev_questions"):
                for idx, q in enumerate(t_data["dev_questions"]):
                    st.markdown(f"**Q [{idx+1}]:** {q}")
                    if idx < len(t_data.get("staff_replies", [])):
                        st.markdown(f"*↳ Answer:* {t_data['staff_replies'][idx]}")

            with st.form("ask_staff_form"):
                dev_q = st.text_input("Ask a follow-up question (sends real email notification):")
                send_q = st.form_submit_button("Send Question ✉️")
                if send_q and dev_q:
                    db[selected_id]["dev_questions"].append(dev_q)
                    db[selected_id]["ai_analysis"]["completeness_check"] = "Needs Clarification"
                    
                    target_email = t_data['metadata']['email']
                    email_sent = send_email_notification(
                        recipient_email=target_email,
                        recipient_name=t_data['metadata']['submitted_by'],
                        ticket_id=selected_id,
                        question_text=dev_q
                    )
                    
                    # Simulation mock response to keep the UI interactive
                    mock_reply = "Automated Demo Reply: Adjusting specifications based on input parameters."
                    db[selected_id]["staff_replies"].append(mock_reply)
                    db[selected_id]["ai_analysis"]["completeness_check"] = "Complete"
                    
                    save_db(db)
                    if email_sent:
                        st.success(f"Email notification successfully dispatched to {target_email}.")
                    st.rerun()

    # ==========================================
    # TAB 3: DASHBOARD
    # ==========================================
    with tab3:
        st.subheader("Global Project Velocity Tracker")
        if not db:
            st.info("No tasks logged.")
        else:
            table_rows = [{
                "Ticket ID": tid,
                "Date Logged": data["metadata"]["timestamp"],
                "Staff Member": data["metadata"]["submitted_by"],
                "Team Area": data["metadata"]["team"],
                "Urgency": data["ai_analysis"]["priority"],
                "Spec Readiness": data["ai_analysis"]["completeness_check"],
                "Status": data.get("status", "Backlog")
            } for tid, data in db.items()]
            
            st.dataframe(table_rows, use_container_width=True, hide_index=True)
