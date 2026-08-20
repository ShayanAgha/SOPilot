"""
seed_sops.py — Generate 4 realistic SOP PDFs and upload them into SOPilot.

Run AFTER seeding an admin account and starting the app:
    python seed_sops.py

The script:
  1. Creates 4 realistic SOP PDFs in a temp directory using fpdf2.
  2. Signs in to the running SOPilot app via HTTP and uploads each PDF
     through the /admin/documents/upload endpoint with the correct category.
  3. Polls each document's status endpoint until ingestion is DONE or FAILED.

Environment variables (or defaults):
  APP_URL   — base URL of the running app (default: http://127.0.0.1:5000)
  ADMIN_EMAIL / ADMIN_PASSWORD — admin credentials to sign in with
"""
import os
import sys
import time
import tempfile
import requests

# ---------------------------------------------------------------------------
# SOP content definitions
# ---------------------------------------------------------------------------

SOPS = [
    {
        "category": "Finance",
        "filename": "Customer_Refund_Policy.pdf",
        "department": "Finance",
        "title": "Customer Refund Policy SOP",
        "version": "v2.1",
        "effective": "2024-01-15",
        "sections": [
            ("Purpose", (
                "This Standard Operating Procedure (SOP) defines the process for handling customer "
                "refund requests at our organization. It ensures consistent, fair, and timely "
                "resolution of all refund cases while maintaining customer satisfaction and financial integrity."
            )),
            ("Scope", (
                "This policy applies to all customer-facing departments including Sales, Customer Success, "
                "and Finance. It covers refund requests for any product or service sold by the organization."
            )),
            ("Refund Eligibility", (
                "Refunds may be approved under the following conditions:\n"
                "1. Request received within 30 days of purchase: Full refund, no questions asked.\n"
                "2. Request received 31–60 days of purchase: Partial refund (50%) subject to manager approval.\n"
                "3. Request received 61–90 days of purchase: Credit note only, subject to VP Finance approval.\n"
                "4. Request received after 90 days: Refunds are not eligible. Exceptions require C-level sign-off.\n"
                "5. Defective or mis-described products: Full refund regardless of purchase date."
            )),
            ("Refund Request Procedure", (
                "Step 1: Customer contacts support via email at refunds@company.com or through the portal.\n"
                "Step 2: Support agent verifies purchase in the CRM system and logs the refund request ticket.\n"
                "Step 3: Agent checks eligibility against the Refund Eligibility table above.\n"
                "Step 4: For eligible refunds under 30 days, agent approves and submits to Finance within 24 hours.\n"
                "Step 5: For 31–60 day requests, escalate to Team Lead for approval within 48 hours.\n"
                "Step 6: Finance processes approved refunds within 5 business days via original payment method.\n"
                "Step 7: Agent notifies customer by email with a confirmation number and expected timeline.\n"
                "Step 8: Ticket is marked Resolved in CRM. Finance updates the refund ledger weekly."
            )),
            ("Exceptions", (
                "All exceptions to this policy must be documented in writing. The requesting employee must:\n"
                "1. Complete the Refund Exception Form (Finance-007) with full justification.\n"
                "2. Obtain approval from the department head and VP Finance.\n"
                "3. Submit the approved form to accounting@company.com within the same business day.\n"
                "Exceptions are reviewed monthly by the Finance Compliance Committee."
            )),
            ("Contact", (
                "Finance Team: finance@company.com | Ext. 2100\n"
                "Refund Portal: https://internal.company.com/refunds\n"
                "Policy Owner: Chief Financial Officer"
            )),
        ],
    },
    {
        "category": "HR",
        "filename": "Employee_Onboarding_Checklist.pdf",
        "department": "Human Resources",
        "title": "Employee Onboarding Checklist SOP",
        "version": "v3.0",
        "effective": "2024-03-01",
        "sections": [
            ("Purpose", (
                "This SOP establishes the standard onboarding process for all new employees joining the "
                "organization. A consistent onboarding experience accelerates productivity, reinforces "
                "company culture, and ensures all compliance and IT requirements are fulfilled on Day 1."
            )),
            ("Scope", (
                "Applies to all full-time and part-time employees. Contract and temporary staff follow "
                "the abbreviated Contractor Onboarding SOP (HR-012)."
            )),
            ("Pre-Arrival (HR — 1 week before start date)", (
                "Step 1: HR sends Welcome Email with first-day logistics, dress code, and parking instructions.\n"
                "Step 2: HR submits IT Setup Request (ticket to helpdesk@company.com) for laptop, email, and software.\n"
                "Step 3: Hiring manager assigns an onboarding buddy from the same team.\n"
                "Step 4: HR prepares physical or digital onboarding pack (offer letter, NDA, policy handbook).\n"
                "Step 5: Facilities prepares desk, access badge, and building key-card."
            )),
            ("Day 1 — Orientation", (
                "Step 1: New hire reports to HR reception at 9:00 AM. HR completes ID verification.\n"
                "Step 2: New hire signs NDA, Employment Agreement, and Direct Deposit form.\n"
                "Step 3: IT issues laptop and walks through VPN setup, password policy, and MFA enrollment.\n"
                "Step 4: HR delivers 2-hour Orientation session covering company mission, org chart, and benefits.\n"
                "Step 5: Hiring manager gives office tour and introduces the team.\n"
                "Step 6: Buddy takes new hire to lunch (company meal allowance up to $25)."
            )),
            ("Week 1 — Role Ramp-Up", (
                "Step 1: Manager schedules daily 15-minute check-ins for the first two weeks.\n"
                "Step 2: New hire completes mandatory compliance training modules (list in HR Portal).\n"
                "Step 3: New hire attends all team standups and is added to relevant Slack channels.\n"
                "Step 4: IT verifies software access is complete by end of Day 3.\n"
                "Step 5: Manager assigns first low-stakes task or project by end of Week 1.\n"
                "Step 6: HR schedules 30-day check-in meeting."
            )),
            ("30/60/90-Day Reviews", (
                "30-day review: HR and manager check in informally. Focus: integration and blockers.\n"
                "60-day review: Manager provides first formal written feedback using the OB-Review template.\n"
                "90-day review: Full performance discussion. Probation confirmed or extended in writing by HR."
            )),
            ("Contacts", (
                "HR Team: hr@company.com | Ext. 1800\n"
                "IT Helpdesk: helpdesk@company.com | Ext. 1900\n"
                "Policy Owner: VP Human Resources"
            )),
        ],
    },
    {
        "category": "IT-Security",
        "filename": "Incident_Response_Runbook.pdf",
        "department": "IT Security",
        "title": "Security Incident Response Runbook SOP",
        "version": "v4.2",
        "effective": "2024-06-01",
        "sections": [
            ("Purpose", (
                "This runbook defines the process for detecting, responding to, and recovering from "
                "security incidents. All employees must be aware of their responsibilities in the event "
                "of a suspected breach, ransomware attack, phishing campaign, or data leak."
            )),
            ("Incident Classification", (
                "P1 — Critical: Active breach, ransomware spreading, confirmed data exfiltration. Response within 15 minutes.\n"
                "P2 — High: Suspected breach, malware on a single endpoint, account compromise. Response within 1 hour.\n"
                "P3 — Medium: Failed intrusion attempt, phishing email reported, unusual login detected. Response within 4 hours.\n"
                "P4 — Low: Policy violation, unintentional data exposure. Response within 24 hours."
            )),
            ("Reporting an Incident", (
                "Step 1: Any employee who suspects a security incident must immediately:\n"
                "   a) Do NOT attempt to fix or investigate the issue yourself.\n"
                "   b) Do NOT power off or disconnect the affected machine (preserves forensic evidence).\n"
                "   c) Report to security@company.com or call the Security Hotline: Ext. 9911 (24/7).\n"
                "Step 2: Provide: your name, device/system affected, what you observed, and when you noticed it.\n"
                "Step 3: Security team acknowledges within SLA times above and assigns an Incident Commander (IC)."
            )),
            ("Incident Response Steps (Security Team)", (
                "Step 1 — Identify: Confirm the incident is real. Review logs in SIEM. Assign severity.\n"
                "Step 2 — Contain: Isolate affected systems from network. Revoke compromised credentials immediately.\n"
                "Step 3 — Eradicate: Remove malware or unauthorized access. Patch exploited vulnerability.\n"
                "Step 4 — Recover: Restore systems from clean backup. Verify integrity before reconnecting.\n"
                "Step 5 — Notify: For P1/P2, notify CISO and Legal within 1 hour. Notify affected customers per "
                "breach notification laws (GDPR: 72 hours; CCPA: 30 days).\n"
                "Step 6 — Document: Record timeline, actions taken, and root cause in the IR ticket system.\n"
                "Step 7 — Post-Mortem: Within 5 business days, conduct a blameless post-mortem. Publish findings."
            )),
            ("Communication Protocol", (
                "Internal: Use the #security-incidents Slack channel (DO NOT email incident details).\n"
                "External: All customer or regulator communications drafted by Legal, approved by CISO.\n"
                "Media: Direct all press inquiries to PR. Do NOT comment on incidents publicly."
            )),
            ("Contacts", (
                "Security Hotline: Ext. 9911 (24/7) | security@company.com\n"
                "CISO: ciso@company.com | Mobile: listed in the confidential IR contacts sheet\n"
                "Policy Owner: Chief Information Security Officer"
            )),
        ],
    },
    {
        "category": "Operations",
        "filename": "Purchase_Approval_Process.pdf",
        "department": "Operations",
        "title": "Purchase Approval Process SOP",
        "version": "v1.5",
        "effective": "2024-02-01",
        "sections": [
            ("Purpose", (
                "This SOP defines the approval workflow for all company purchases to ensure proper "
                "budget control, audit compliance, and vendor management. No purchase may be made "
                "without following this process."
            )),
            ("Scope", (
                "Applies to all employees making purchases on behalf of the company, including software "
                "subscriptions, hardware, services, travel, and any other business expense."
            )),
            ("Approval Thresholds", (
                "Under $500: Self-approval allowed. Employee submits receipt to Finance within 48 hours.\n"
                "$500 – $2,499: Team Lead approval required before purchase.\n"
                "$2,500 – $9,999: Department Head approval required.\n"
                "$10,000 – $49,999: VP and Finance Director approval required.\n"
                "$50,000 and above: C-level (CEO or CFO) approval and Board notification required.\n"
                "Recurring subscriptions: Treated as annual cost for threshold calculation."
            )),
            ("Purchase Request Procedure", (
                "Step 1: Employee completes Purchase Request Form (PR-001) in the procurement portal.\n"
                "Step 2: Form requires: vendor name, item description, business justification, cost, and budget code.\n"
                "Step 3: System routes the request to the appropriate approver based on the threshold table.\n"
                "Step 4: Approver reviews and approves or rejects within 2 business days.\n"
                "Step 5: If approved, Finance issues a Purchase Order (PO) number to the requestor.\n"
                "Step 6: Employee may proceed with purchase using the PO number. No PO = no purchase.\n"
                "Step 7: Employee submits invoice + receipt to ap@company.com within 5 business days of delivery.\n"
                "Step 8: Finance reconciles invoices monthly. Unreconciled POs are escalated to department heads."
            )),
            ("Preferred Vendors", (
                "Using a preferred vendor reduces approval time by one tier. Preferred vendor list is maintained "
                "by Procurement at: https://internal.company.com/procurement/vendors\n"
                "To add a vendor to the preferred list, submit a Vendor Qualification Form (VQ-002) to procurement@company.com."
            )),
            ("Emergency Purchases", (
                "For urgent purchases where waiting for approval would cause material business harm:\n"
                "Step 1: Call your department head directly for verbal approval.\n"
                "Step 2: Make the purchase and submit the PR-001 retrospectively within 24 hours.\n"
                "Step 3: Note 'Emergency Purchase' and the verbal approver's name on the form.\n"
                "Step 4: Abuse of the emergency process will result in disciplinary action."
            )),
            ("Contacts", (
                "Procurement: procurement@company.com | Ext. 2200\n"
                "Accounts Payable: ap@company.com | Ext. 2201\n"
                "Procurement Portal: https://internal.company.com/procurement\n"
                "Policy Owner: VP Operations"
            )),
        ],
    },
]


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate_pdf(sop: dict, output_path: str) -> None:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Header bar
    pdf.set_fill_color(20, 24, 31)   # --color-ink
    pdf.rect(0, 0, 210, 18, 'F')
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(10, 4)
    pdf.cell(0, 10, "SOPilot — Standard Operating Procedure", ln=False)
    pdf.ln(20)

    # Title block
    pdf.set_text_color(20, 24, 31)
    pdf.set_font("Helvetica", "B", 18)
    pdf.multi_cell(0, 9, sop["title"])
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(91, 100, 114)
    pdf.cell(0, 6, f"Category: {sop['category']}  |  Department: {sop['department']}  |  {sop['version']}  |  Effective: {sop['effective']}", ln=True)
    pdf.ln(4)

    # Divider
    pdf.set_draw_color(216, 220, 227)
    pdf.set_line_width(0.4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)

    # Sections
    for section_title, section_body in sop["sections"]:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(20, 24, 31)
        pdf.cell(0, 7, section_title, ln=True)
        pdf.ln(1)

        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(31, 37, 48)
        pdf.multi_cell(0, 5.5, section_body)
        pdf.ln(5)

    # Footer
    pdf.set_y(-18)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 155, 165)
    pdf.cell(0, 5, f"SOPilot — {sop['title']} — {sop['version']} — Confidential Internal Document", align="C")

    pdf.output(output_path)


# ---------------------------------------------------------------------------
# Upload via HTTP
# ---------------------------------------------------------------------------

def upload_sops(app_url: str, email: str, password: str) -> None:
    session = requests.Session()

    # Login
    print(f"→ Signing in as {email}…")
    login_url = f"{app_url}/auth/login"
    r = session.get(login_url)
    r.raise_for_status()

    r = session.post(login_url, data={"email": email, "password": password}, allow_redirects=True)
    if "Invalid email" in r.text or r.url.endswith("/login"):
        print("✗ Login failed. Check ADMIN_EMAIL and ADMIN_PASSWORD.")
        sys.exit(1)
    print("✓ Signed in.")

    with tempfile.TemporaryDirectory() as tmpdir:
        for sop in SOPS:
            pdf_path = os.path.join(tmpdir, sop["filename"])
            print(f"→ Generating {sop['filename']}…")
            generate_pdf(sop, pdf_path)

            print(f"→ Uploading {sop['filename']} (category: {sop['category']})…")
            with open(pdf_path, "rb") as f:
                r = session.post(
                    f"{app_url}/admin/documents/upload",
                    files={"file": (sop["filename"], f, "application/pdf")},
                    data={"category": sop["category"], "owner_department": sop["department"]},
                    allow_redirects=True,
                )
            r.raise_for_status()

    # Poll status for all docs until done/failed
    print("\n→ Polling ingestion status…")
    docs_r = session.get(f"{app_url}/admin/documents")
    # Extract doc IDs from status endpoint by checking /admin/documents/<id>/status for ids 1..20
    done_ids = set()
    for doc_id in range(1, 25):
        try:
            sr = session.get(f"{app_url}/admin/documents/{doc_id}/status")
            if sr.status_code == 404:
                continue
            data = sr.json()
            if data.get("status") in ("done", "failed"):
                done_ids.add(doc_id)
        except Exception:
            pass

    pending_ids = set(range(1, 25)) - done_ids
    deadline = time.time() + 300  # 5-minute timeout
    while pending_ids and time.time() < deadline:
        time.sleep(4)
        still_pending = set()
        for doc_id in list(pending_ids):
            try:
                sr = session.get(f"{app_url}/admin/documents/{doc_id}/status")
                if sr.status_code == 404:
                    continue
                data = sr.json()
                status = data.get("status", "")
                if status == "done":
                    print(f"  ✓ Doc #{doc_id} — ingested ({data.get('chunk_count')} chunks, {data.get('page_count')} pages)")
                elif status == "failed":
                    print(f"  ✗ Doc #{doc_id} — FAILED: {data.get('error_message')}")
                else:
                    still_pending.add(doc_id)
                    print(f"  … Doc #{doc_id} — {status}")
            except Exception:
                still_pending.add(doc_id)
        pending_ids = still_pending

    if pending_ids:
        print(f"⚠ Timed out waiting for docs: {pending_ids}")
    else:
        print("\n✅ All SOPs seeded and ingested successfully!")
        print("   You can now log in and ask questions about:")
        for s in SOPS:
            print(f"   • {s['title']} ({s['category']})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:5000").rstrip("/")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        print("Usage: ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=secret python seed_sops.py")
        print("  APP_URL defaults to http://127.0.0.1:5000")
        sys.exit(1)

    upload_sops(APP_URL, ADMIN_EMAIL, ADMIN_PASSWORD)
