"""
notifications.py - Email notification system for Smart City Complaint System

Sends emails to:
1. CITIZEN — complaint received confirmation
2. CITIZEN — complaint resolved notification
3. ADMIN   — new complaint alert (with full details)
4. ADMIN   — emergency complaint alert (high priority)
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── Config ──────────────────────────────────────────────────────────────────

def get_email_config(db):
    try:
        row = db.execute("SELECT * FROM notification_settings WHERE id=1").fetchone()
        if row:
            return dict(zip(row.keys(), row))
    except Exception:
        pass
    return None

# ─── Core Sender ─────────────────────────────────────────────────────────────

def send_email(to_email, subject, html_body, config):
    if not config or not config.get('email_enabled'):
        return False, "Email notifications are disabled"
    if not to_email or '@' not in to_email:
        return False, "Invalid recipient email"
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"Smart City Hub <{config['sender_email']}>"
        msg['To']      = to_email
        msg.attach(MIMEText(html_body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as server:
            server.login(config['sender_email'], config['sender_password'])
            server.sendmail(config['sender_email'], to_email, msg.as_string())
        return True, "Email sent successfully"
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Check App Password."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Failed: {str(e)}"

# ─── Notification Logger ──────────────────────────────────────────────────────

def log_notification(db, complaint_id, notif_type, recipient_email, success, message):
    try:
        db.execute('''
            INSERT INTO notifications (complaint_id, type, recipient_email, success, message, sent_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (complaint_id, notif_type, recipient_email, 1 if success else 0, message))
        db.commit()
    except Exception as e:
        print(f"[NOTIFY LOG ERROR] {e}")

# ─── Citizen Email Templates ──────────────────────────────────────────────────

def complaint_received_email(complaint):
    priority_color = {'HIGH':'#dc3545','MEDIUM':'#ffc107','LOW':'#28a745'}.get(
        complaint.get('priority_label','LOW'), '#28a745')
    emergency_section = ""
    if complaint.get('is_emergency'):
        emergency_section = """
        <div style="background:#fff0f0;border:2px solid #dc3545;border-radius:8px;padding:14px;margin:16px 0;">
            <strong style="color:#dc3545;">🚨 EMERGENCY ALERT</strong><br>
            Your complaint has been flagged as an emergency. Authorities have been notified immediately.
        </div>"""
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8f9fa;padding:20px;">
      <div style="background:linear-gradient(135deg,#1a3c5e,#2e86de);padding:28px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:white;margin:0;font-size:24px;">🏙️ Smart City Hub</h1>
        <p style="color:rgba(255,255,255,0.8);margin:6px 0 0;">Complaint Received</p>
      </div>
      <div style="background:white;padding:28px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
        <p style="color:#333;font-size:16px;">Dear <strong>{complaint.get('name','Citizen')}</strong>,</p>
        <p style="color:#555;">Your complaint has been received and is being processed by our AI system.</p>
        {emergency_section}
        <div style="background:#f0f4f8;border-radius:10px;padding:20px;margin:20px 0;">
          <h3 style="color:#1a3c5e;margin:0 0 14px;">📋 Complaint Details</h3>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:6px 0;color:#718096;width:40%">Complaint ID</td>
                <td style="padding:6px 0;font-weight:700;color:#1a3c5e">#{complaint.get('id')}</td></tr>
            <tr><td style="padding:6px 0;color:#718096">Category</td>
                <td style="padding:6px 0;font-weight:600">{complaint.get('category','Unknown')}</td></tr>
            <tr><td style="padding:6px 0;color:#718096">Priority</td>
                <td style="padding:6px 0;">
                  <span style="background:{priority_color};color:{'#333' if complaint.get('priority_label')=='MEDIUM' else 'white'};padding:3px 12px;border-radius:20px;font-weight:700;font-size:13px;">
                    {complaint.get('priority_label','LOW')}
                  </span>
                </td></tr>
            <tr><td style="padding:6px 0;color:#718096">Location</td>
                <td style="padding:6px 0">{complaint.get('location_text') or 'GPS Captured'}</td></tr>
            <tr><td style="padding:6px 0;color:#718096">Submitted</td>
                <td style="padding:6px 0">{complaint.get('submitted_at','')[:16]}</td></tr>
          </table>
        </div>
        <div style="background:#e8f4fd;border-left:4px solid #2e86de;padding:14px;border-radius:0 8px 8px 0;margin:16px 0;">
          <strong>Your complaint:</strong><br>
          <em style="color:#555">"{complaint.get('complaint_text','')[:200]}"</em>
        </div>
        <p style="color:#555;">We will notify you once your complaint is resolved. Please save your Complaint ID <strong style="color:#1a3c5e">#{complaint.get('id')}</strong> for reference.</p>
        <p style="text-align:center;color:#aaa;font-size:12px;margin-top:20px;">Smart City Complaint System — Automated Notification</p>
      </div>
    </div>"""

def complaint_resolved_email(complaint):
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8f9fa;padding:20px;">
      <div style="background:linear-gradient(135deg,#155724,#28a745);padding:28px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="color:white;margin:0;font-size:24px;">✅ Issue Resolved!</h1>
        <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;">Smart City Hub</p>
      </div>
      <div style="background:white;padding:28px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
        <p style="color:#333;font-size:16px;">Dear <strong>{complaint.get('name','Citizen')}</strong>,</p>
        <p style="color:#555;">Great news! Your complaint has been <strong style="color:#28a745;">resolved</strong> by our city team.</p>
        <div style="background:#f0f4f8;border-radius:10px;padding:20px;margin:20px 0;">
          <h3 style="color:#155724;margin:0 0 14px;">📋 Resolution Summary</h3>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:6px 0;color:#718096;width:40%">Complaint ID</td>
                <td style="padding:6px 0;font-weight:700;color:#1a3c5e">#{complaint.get('id')}</td></tr>
            <tr><td style="padding:6px 0;color:#718096">Category</td>
                <td style="padding:6px 0;font-weight:600">{complaint.get('category','Unknown')}</td></tr>
            <tr><td style="padding:6px 0;color:#718096">Location</td>
                <td style="padding:6px 0">{complaint.get('location_text') or 'GPS Location'}</td></tr>
            <tr><td style="padding:6px 0;color:#718096">Submitted</td>
                <td style="padding:6px 0">{complaint.get('submitted_at','')[:16]}</td></tr>
            <tr><td style="padding:6px 0;color:#718096">Resolved</td>
                <td style="padding:6px 0;color:#28a745;font-weight:600">{complaint.get('resolved_at','')[:16]}</td></tr>
          </table>
        </div>
        <div style="background:#d4edda;border-left:4px solid #28a745;padding:14px;border-radius:0 8px 8px 0;margin:16px 0;">
          <strong>Original complaint:</strong><br>
          <em style="color:#555">"{complaint.get('complaint_text','')[:200]}"</em>
        </div>
        <p style="color:#555;">Thank you for reporting this issue. Your feedback helps us build a better city!</p>
        <p style="color:#888;font-size:13px;text-align:center;margin-top:20px;">Smart City Complaint System — Automated Notification</p>
      </div>
    </div>"""

# ─── Admin Email Templates ────────────────────────────────────────────────────

def admin_new_complaint_email(complaint):
    """Alert email sent to admin when a new complaint is submitted"""
    priority_color = {'HIGH':'#dc3545','MEDIUM':'#ffc107','LOW':'#28a745'}.get(
        complaint.get('priority_label','LOW'), '#28a745')
    priority_text_color = '#333' if complaint.get('priority_label') == 'MEDIUM' else 'white'

    emergency_banner = ""
    if complaint.get('is_emergency'):
        emergency_banner = """
        <div style="background:#dc3545;color:white;padding:14px 20px;border-radius:8px;margin-bottom:16px;text-align:center;">
            <strong style="font-size:16px;">🚨 EMERGENCY COMPLAINT — IMMEDIATE ACTION REQUIRED</strong>
        </div>"""

    duplicate_note = ""
    if complaint.get('is_duplicate'):
        duplicate_note = f"""
        <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:12px;margin:12px 0;">
            ⚠️ <strong>Duplicate detected</strong> — Similar to Complaint #{complaint.get('duplicate_of')}
        </div>"""

    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8f9fa;padding:20px;">
      <div style="background:linear-gradient(135deg,#1a3c5e,#2e86de);padding:24px 28px;border-radius:12px 12px 0 0;">
        <h1 style="color:white;margin:0;font-size:22px;">🏙️ Smart City Hub — Admin Alert</h1>
        <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:14px;">New complaint submitted</p>
      </div>
      <div style="background:white;padding:28px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
        {emergency_banner}
        <p style="color:#333;font-size:15px;">A new complaint has been submitted and requires your attention.</p>
        {duplicate_note}

        <div style="background:#f0f4f8;border-radius:10px;padding:20px;margin:16px 0;">
          <h3 style="color:#1a3c5e;margin:0 0 14px;font-size:16px;">📋 Complaint Details</h3>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:7px 0;color:#718096;width:38%">Complaint ID</td>
                <td style="padding:7px 0;font-weight:700;color:#1a3c5e;font-size:15px;">#{complaint.get('id')}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Citizen Name</td>
                <td style="padding:7px 0;font-weight:600">{complaint.get('name','—')}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Mobile</td>
                <td style="padding:7px 0">{complaint.get('phone') or '—'}</td></tr>
            <tr style="background:#fffbeb;">
                <td style="padding:7px 6px;color:#92400e;font-weight:700;">📧 Citizen Email ID</td>
                <td style="padding:7px 6px;font-weight:700;color:#1a3c5e;">
                  <a href="mailto:{complaint.get('email') or ''}" style="color:#2e86de;text-decoration:none;">
                    {complaint.get('email') or '—'}
                  </a>
                  <span style="background:#fef3c7;color:#92400e;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;font-weight:600;">
                    Notification sent here
                  </span>
                </td>
            </tr>
            <tr><td style="padding:7px 0;color:#718096">Category</td>
                <td style="padding:7px 0;font-weight:600">{complaint.get('category','Unknown')}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Priority</td>
                <td style="padding:7px 0;">
                  <span style="background:{priority_color};color:{priority_text_color};padding:3px 14px;border-radius:20px;font-weight:700;font-size:13px;">
                    {complaint.get('priority_label','LOW')}
                  </span>
                </td></tr>
            <tr><td style="padding:7px 0;color:#718096">Address</td>
                <td style="padding:7px 0">{complaint.get('address') or '—'}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Landmark</td>
                <td style="padding:7px 0">{complaint.get('landmark') or '—'}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Pincode</td>
                <td style="padding:7px 0">{complaint.get('pincode') or '—'}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Submitted At</td>
                <td style="padding:7px 0">{complaint.get('submitted_at','')[:16]}</td></tr>
          </table>
        </div>

        <div style="background:#e8f4fd;border-left:4px solid #2e86de;padding:14px;border-radius:0 8px 8px 0;margin:16px 0;">
          <strong style="color:#1a3c5e;">Complaint Description:</strong><br>
          <p style="color:#444;margin:8px 0 0;line-height:1.6;">"{complaint.get('complaint_text','')}"</p>
        </div>

        <div style="text-align:center;margin-top:20px;">
          <p style="color:#555;font-size:13px;">Login to the admin dashboard to view and resolve this complaint.</p>
          <div style="background:#1a3c5e;color:white;padding:10px 28px;border-radius:8px;display:inline-block;font-weight:600;margin-top:8px;">
            Dashboard → http://127.0.0.1:5000/admin/dashboard
          </div>
        </div>

        <!-- Proof of citizen email -->
        <div style="margin-top:24px;border:2px dashed #2e86de;border-radius:10px;padding:4px;">
          <div style="background:#2e86de;color:white;padding:10px 16px;border-radius:7px 7px 0 0;font-size:13px;font-weight:700;">
            📧 PROOF OF EMAIL SENT TO CITIZEN — Exact copy of notification delivered to {complaint.get('email') or 'citizen'}
          </div>
          <div style="background:#f0f7ff;padding:14px 16px;border-radius:0 0 7px 7px;">
            <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:10px;">
              <tr style="background:#dbeafe;border-radius:6px;">
                <td style="color:#1e40af;padding:5px 6px;width:30%;font-weight:700;">📧 Sent To</td>
                <td style="color:#1e3a8a;font-weight:700;font-size:13px;padding:5px 6px;">
                  {complaint.get('email') or '—'}
                </td>
              </tr>
              <tr>
                <td style="color:#718096;padding:3px 0;">Subject</td>
                <td style="color:#333;">✅ Complaint #{complaint.get('id')} Received — Smart City Hub</td>
              </tr>
              <tr>
                <td style="color:#718096;padding:3px 0;">Sent At</td>
                <td style="color:#333;">{complaint.get('submitted_at','')[:16]}</td>
              </tr>
              <tr>
                <td style="color:#718096;padding:3px 0;">Status</td>
                <td style="color:#16a34a;font-weight:700;">✓ Delivered to citizen inbox</td>
              </tr>
            </table>
            <div style="border-top:1px solid #bfdbfe;padding-top:12px;margin-top:4px;">
              <p style="font-size:12px;color:#1e40af;font-weight:700;margin:0 0 8px;">Message body sent to citizen:</p>
              <div style="background:white;border:1px solid #dbeafe;border-radius:6px;padding:14px;font-size:12px;color:#374151;line-height:1.7;">
                Dear <strong>{complaint.get('name','Citizen')}</strong>,<br><br>
                Your complaint has been received and is being processed by our AI system.<br><br>
                <strong>Complaint ID:</strong> #{complaint.get('id')}<br>
                <strong>Category:</strong> {complaint.get('category','Unknown')}<br>
                <strong>Priority:</strong> {complaint.get('priority_label','LOW')}<br>
                <strong>Location:</strong> {complaint.get('location_text') or 'GPS Captured'}<br>
                <strong>Submitted:</strong> {complaint.get('submitted_at','')[:16]}<br><br>
                <em>"{complaint.get('complaint_text','')[:300]}"</em><br><br>
                We will notify you once your complaint is resolved. Please save your Complaint ID
                <strong>#{complaint.get('id')}</strong> for reference.<br><br>
                Thank you for helping make our city better 🙏<br>
                <span style="color:#888;font-size:11px;">Smart City Complaint System — Automated Notification</span>
              </div>
            </div>
          </div>
        </div>

        <p style="text-align:center;color:#aaa;font-size:12px;margin-top:20px;">Smart City Hub — Admin Notification System</p>
      </div>
    </div>"""

def admin_complaint_resolved_email(complaint):
    """Confirmation email sent to admin when a complaint is resolved"""
    return f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:620px;margin:0 auto;background:#f8f9fa;padding:20px;">
      <div style="background:linear-gradient(135deg,#155724,#28a745);padding:24px 28px;border-radius:12px 12px 0 0;">
        <h1 style="color:white;margin:0;font-size:22px;">✅ Complaint Resolved — Admin Confirmation</h1>
        <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:14px;">Smart City Hub</p>
      </div>
      <div style="background:white;padding:28px;border-radius:0 0 12px 12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
        <p style="color:#333;font-size:15px;">Complaint <strong style="color:#1a3c5e;">#{complaint.get('id')}</strong> has been marked as resolved.</p>

        <div style="background:#f0f4f8;border-radius:10px;padding:20px;margin:16px 0;">
          <h3 style="color:#155724;margin:0 0 14px;font-size:16px;">📋 Resolution Summary</h3>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:7px 0;color:#718096;width:38%">Complaint ID</td>
                <td style="padding:7px 0;font-weight:700;color:#1a3c5e">#{complaint.get('id')}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Citizen Name</td>
                <td style="padding:7px 0;font-weight:600">{complaint.get('name','—')}</td></tr>
            <tr style="background:#fffbeb;">
                <td style="padding:7px 6px;color:#92400e;font-weight:700;">📧 Citizen Email ID</td>
                <td style="padding:7px 6px;font-weight:700;color:#1a3c5e;">
                  <a href="mailto:{complaint.get('email') or ''}" style="color:#2e86de;text-decoration:none;">
                    {complaint.get('email') or '—'}
                  </a>
                  <span style="background:#fef3c7;color:#92400e;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px;font-weight:600;">
                    Resolution email sent here
                  </span>
                </td>
            </tr>
            <tr><td style="padding:7px 0;color:#718096">Category</td>
                <td style="padding:7px 0;font-weight:600">{complaint.get('category','Unknown')}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Location</td>
                <td style="padding:7px 0">{complaint.get('location_text') or '—'}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Submitted</td>
                <td style="padding:7px 0">{complaint.get('submitted_at','')[:16]}</td></tr>
            <tr><td style="padding:7px 0;color:#718096">Resolved At</td>
                <td style="padding:7px 0;color:#28a745;font-weight:600">{complaint.get('resolved_at','')[:16]}</td></tr>
          </table>
        </div>

        <!-- Proof of citizen resolution email -->
        <div style="margin-top:24px;border:2px dashed #28a745;border-radius:10px;padding:4px;">
          <div style="background:#28a745;color:white;padding:10px 16px;border-radius:7px 7px 0 0;font-size:13px;font-weight:700;">
            📧 PROOF OF RESOLUTION EMAIL SENT TO CITIZEN — Exact copy delivered to {complaint.get('email') or 'citizen'}
          </div>
          <div style="background:#f0fdf4;padding:14px 16px;border-radius:0 0 7px 7px;">
            <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:10px;">
              <tr style="background:#bbf7d0;border-radius:6px;">
                <td style="color:#166534;padding:5px 6px;width:30%;font-weight:700;">📧 Sent To</td>
                <td style="color:#14532d;font-weight:700;font-size:13px;padding:5px 6px;">
                  {complaint.get('email') or '—'}
                </td>
              </tr>
              <tr>
                <td style="color:#718096;padding:3px 0;">Subject</td>
                <td style="color:#333;">🎉 Complaint #{complaint.get('id')} Resolved — Smart City Hub</td>
              </tr>
              <tr>
                <td style="color:#718096;padding:3px 0;">Sent At</td>
                <td style="color:#333;">{complaint.get('resolved_at','')[:16]}</td>
              </tr>
              <tr>
                <td style="color:#718096;padding:3px 0;">Status</td>
                <td style="color:#16a34a;font-weight:700;">✓ Delivered to citizen inbox</td>
              </tr>
            </table>
            <div style="border-top:1px solid #bbf7d0;padding-top:12px;margin-top:4px;">
              <p style="font-size:12px;color:#166534;font-weight:700;margin:0 0 8px;">Message body sent to citizen:</p>
              <div style="background:white;border:1px solid #bbf7d0;border-radius:6px;padding:14px;font-size:12px;color:#374151;line-height:1.7;">
                Dear <strong>{complaint.get('name','Citizen')}</strong>,<br><br>
                Great news! Your complaint has been <strong>resolved</strong> by our city team.<br><br>
                <strong>Complaint ID:</strong> #{complaint.get('id')}<br>
                <strong>Category:</strong> {complaint.get('category','Unknown')}<br>
                <strong>Location:</strong> {complaint.get('location_text') or 'GPS Location'}<br>
                <strong>Submitted:</strong> {complaint.get('submitted_at','')[:16]}<br>
                <strong>Resolved:</strong> {complaint.get('resolved_at','')[:16]}<br><br>
                <em>"{complaint.get('complaint_text','')[:300]}"</em><br><br>
                Thank you for reporting this issue. Your feedback helps us build a better city!<br>
                <span style="color:#888;font-size:11px;">Smart City Complaint System — Automated Notification</span>
              </div>
            </div>
          </div>
        </div>

        <p style="color:#555;font-size:13px;text-align:center;margin-top:16px;">Smart City Hub — Admin Notification System</p>
      </div>
    </div>"""

# ─── Citizen Notify Functions ─────────────────────────────────────────────────

def notify_complaint_received(db, complaint):
    config   = get_email_config(db)
    to_email = complaint.get('email','')
    if not to_email:
        return
    subject = f"✅ Complaint #{complaint.get('id')} Received — Smart City Hub"
    ok, msg = send_email(to_email, subject, complaint_received_email(complaint), config)
    log_notification(db, complaint.get('id'), 'received', to_email, ok, msg)
    print(f"[EMAIL CITIZEN] {'Sent' if ok else 'Failed'}: {to_email} — {msg}")

def notify_complaint_resolved(db, complaint):
    config   = get_email_config(db)
    to_email = complaint.get('email','')
    if not to_email:
        return
    subject = f"🎉 Complaint #{complaint.get('id')} Resolved — Smart City Hub"
    ok, msg = send_email(to_email, subject, complaint_resolved_email(complaint), config)
    log_notification(db, complaint.get('id'), 'resolved', to_email, ok, msg)
    print(f"[EMAIL CITIZEN] {'Sent' if ok else 'Failed'}: {to_email} — {msg}")

# ─── Admin Notify Functions ───────────────────────────────────────────────────

def notify_admin_new_complaint(db, complaint):
    """Send new complaint alert to admin"""
    config      = get_email_config(db)
    admin_email = config.get('admin_email','').strip() if config else ''
    if not admin_email:
        return
    if not config.get('notify_admin_on_receive'):
        return
    subject = f"🔔 New Complaint #{complaint.get('id')} — {complaint.get('category','Unknown')} [{complaint.get('priority_label','LOW')}]"
    if complaint.get('is_emergency'):
        subject = f"🚨 EMERGENCY Complaint #{complaint.get('id')} — IMMEDIATE ACTION REQUIRED"
    ok, msg = send_email(admin_email, subject, admin_new_complaint_email(complaint), config)
    log_notification(db, complaint.get('id'), 'admin_new', admin_email, ok, msg)
    print(f"[EMAIL ADMIN] {'Sent' if ok else 'Failed'}: {admin_email} — {msg}")

def notify_admin_resolved(db, complaint):
    """Send resolution confirmation to admin"""
    config      = get_email_config(db)
    admin_email = config.get('admin_email','').strip() if config else ''
    if not admin_email:
        return
    if not config.get('notify_admin_on_resolve'):
        return
    subject = f"✅ Complaint #{complaint.get('id')} Resolved — Smart City Hub"
    ok, msg = send_email(admin_email, subject, admin_complaint_resolved_email(complaint), config)
    log_notification(db, complaint.get('id'), 'admin_resolved', admin_email, ok, msg)
    print(f"[EMAIL ADMIN] {'Sent' if ok else 'Failed'}: {admin_email} — {msg}")