#!/usr/bin/env python3
import os
import sys
import smtplib
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
 
try:
    from anthropic import Anthropic
except ImportError:
    print("ERROR: anthropic module not installed")
    sys.exit(1)
 
# Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', '')
EMAIL_TO = os.getenv('EMAIL_TO', '')
HISTORY_FILE = 'reported_news.json'
 
def check_config():
    """Verify all required config is present"""
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append('ANTHROPIC_API_KEY')
    if not EMAIL_FROM:
        missing.append('EMAIL_FROM')
    if not EMAIL_TO:
        missing.append('EMAIL_TO')
    if not SMTP_USER:
        missing.append('SMTP_USER')
    if not SMTP_PASS:
        missing.append('SMTP_PASS')
 
    if missing:
        print(f"❌ ERROR: Missing environment variables: {', '.join(missing)}")
        return False
    return True
 
def load_tenants(filename='tenants.txt'):
    """Load tenant list from file"""
    if not os.path.exists(filename):
        print(f"❌ ERROR: {filename} not found")
        return []
 
    with open(filename, 'r') as f:
        tenants = [line.strip() for line in f if line.strip()]
    return tenants
 
def load_history():
    """Load previously reported news"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}
 
def save_history(history):
    """Save reported news to file"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"⚠️  Warning: Could not save history: {e}")
 
def analyze_tenants(tenants, history):
    """Use Claude to analyze all tenants"""
    if not tenants:
        return "No tenants found in tenants.txt"
 
    tenant_list = '\n'.join([f"{i+1}. {tenant}" for i, tenant in enumerate(tenants)])
 
    prompt = f"""You are a commercial real estate intelligence agent. ONLY search for and report NEWS about these {len(tenants)} companies that was PUBLISHED IN THE LAST 2 WEEKS (14 days):
 
{tenant_list}
 
CRITICAL REQUIREMENTS:
1. ONLY report news published in the LAST 2 WEEKS - anything older is ignored
2. For each company search for:
   - Bankruptcy filings, financial distress, payment defaults
   - Facility closures, relocations, consolidations
   - Major layoffs, hiring freezes, workforce reductions
   - New contracts, expansion announcements
   - Acquisition or merger activity
   - Earnings warnings, profit alerts, revenue misses
   - Leadership changes, strategic pivots
 
3. Include EXACT publication date for every item (must be within last 2 weeks)
4. Only report findings that affect rent payment ability or expansion likelihood
5. Be specific with details and include source/publication name
6. If a company has no news in the last 2 weeks, list it under NO NEW NEWS
 
Format your response EXACTLY as:
 
=== CRITICAL ALERTS (Rent Payment Risk - Last 2 Weeks) ===
- COMPANY NAME: [2-3 sentence description with specific details] Published: [EXACT DATE - must be within last 2 weeks]
  Source: [publication name]
 
=== GROWTH SIGNALS (Expansion Opportunities - Last 2 Weeks) ===
- COMPANY NAME: [2-3 sentence description with specific details] Published: [EXACT DATE - must be within last 2 weeks]
  Source: [publication name]
 
=== NO NEW MATERIAL NEWS IN LAST 2 WEEKS ===
[List company names with no significant news published in the last 14 days]
 
ANALYSIS COMPLETE: [X critical alerts from last 2 weeks, Y growth signals from last 2 weeks, Z no news]
"""
 
    try:
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-6",  # Sonnet 4.6: ~5x cheaper than Opus ($3/$15 vs $5/$25 per MTok)
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
 
        response_text = ""
        for block in message.content:
            if hasattr(block, 'text'):
                response_text += block.text
 
        return response_text if response_text.strip() else "No results found"
    except Exception as e:
        print(f"❌ API Error: {e}")
        return f"Error analyzing tenants: {str(e)}"
 
def send_email(subject, body):
    """Send email via SMTP"""
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
 
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
 
        print("✓ Email sent successfully")
        return True
    except Exception as e:
        print(f"❌ Email Error: {e}")
        return False
 
def main():
    """Main execution"""
    print("=" * 60)
    print("TENANT INTELLIGENCE AGENT")
    print("=" * 60)
 
    # Check configuration
    if not check_config():
        sys.exit(1)
 
    # Load tenants
    print("\n✓ Loading tenant list...")
    tenants = load_tenants()
    if not tenants:
        print("❌ No tenants found")
        sys.exit(1)
    print(f"✓ Found {len(tenants)} tenants")
 
    # Load history
    print("✓ Loading history...")
    history = load_history()
    print(f"✓ Found {len(history)} previously reported items")
 
    # Analyze
    print("\n🔍 Analyzing tenants...")
    analysis = analyze_tenants(tenants, history)
 
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(analysis)
 
    # Send email
    print("\n📧 Sending email...")
    subject = f"Tenant Intelligence - {datetime.now().strftime('%b %d, %Y')}"
    body = f"""TENANT INTELLIGENCE REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M PT')}
 
{analysis}
 
---
Next report: Next Monday at 8 AM PT
"""
 
    if send_email(subject, body):
        print("✓ Success!")
    else:
        print("❌ Failed to send email")
        sys.exit(1)
 
if __name__ == "__main__":
    main()
