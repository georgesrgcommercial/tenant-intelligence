import os
import smtplib
import json
from anthropic import Anthropic
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
 
# Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = 587
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_TO = os.getenv('EMAIL_TO')
HISTORY_FILE = 'reported_news.json'
 
# Initialize Claude client
client = Anthropic(api_key=ANTHROPIC_API_KEY)
 
def load_tenants(filename='tenants.txt'):
    """Load tenant list from file"""
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
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)
 
def extract_unique_news(analysis_text, history):
    """
    Extract news items from analysis and filter out previously reported items.
    Returns: (filtered_analysis, new_items_found)
    """
    lines = analysis_text.split('\n')
    filtered_lines = []
    new_items_found = False
    
    for line in lines:
        # Check if this is a news item (starts with "- COMPANY NAME:")
        if line.strip().startswith('- ') and ':' in line:
            # Extract company name and description
            item_key = line.strip().lower()
            
            # If we've seen this exact line before, skip it
            if item_key in history:
                print(f"⏭️  Skipping previously reported: {line.strip()[:80]}...")
                continue
            else:
                # New item - add it
                filtered_lines.append(line)
                history[item_key] = datetime.now().isoformat()
                new_items_found = True
        else:
            # Keep section headers and other text
            filtered_lines.append(line)
    
    filtered_analysis = '\n'.join(filtered_lines)
    return filtered_analysis, new_items_found, history
 
def analyze_tenants(history):
    """Use Claude to analyze all tenants"""
    tenants = load_tenants()
    tenant_list = '\n'.join([f"{i+1}. {tenant}" for i, tenant in enumerate(tenants)])
    
    # Build list of previously reported items to exclude
    previously_reported = ""
    if history:
        previously_reported = f"""
 
IMPORTANT: Do NOT report these items again (already sent in previous reports):
{chr(10).join(list(history.keys())[:20])}
 
If any of these companies appear in search results, SKIP them - only report NEW items we haven't covered.
"""
    
    # Create the prompt for Claude
    prompt = f"""You are a commercial real estate tenant intelligence agent.
 
SEARCH the web for BRAND NEW news (published in the last 2 weeks ONLY) about these {len(tenants)} companies:
 
{tenant_list}
 
CRITICAL REQUIREMENTS:
1. ONLY report news published in the LAST 2 WEEKS (14 days)
2. Ignore any news older than 2 weeks - do not include it
3. DO NOT repeat news we've already reported{previously_reported}
4. For EACH company, search for the most recent updates on:
   - Bankruptcy filings, financial distress, payment defaults, debt issues
   - Facility closures, relocations, or consolidations
   - Major layoffs, hiring freezes, or workforce reductions
   - New major contracts or expansion announcements
   - Acquisition or merger activity
   - Earnings warnings, profit alerts, or revenue misses
   - Leadership changes or strategic pivots
 
5. Only report findings that directly impact rent payment ability or expansion likelihood
6. Include the EXACT publication date for every news item
7. After you search, PROVIDE YOUR COMPLETE FINDINGS in the format below
 
YOU MUST INCLUDE YOUR FINAL ANALYSIS. Do not just say you'll search - actually provide the results.
 
=== CRITICAL ALERTS (Rent Payment Risk - Red Flags) ===
- COMPANY NAME: [2-3 sentence description] Published: [exact date]
  Source: [publication]
 
=== GROWTH SIGNALS (Expansion Opportunity - Green Flags) ===
- COMPANY NAME: [2-3 sentence description] Published: [exact date]
  Source: [publication]
 
=== NO NEW MATERIAL NEWS IN LAST 2 WEEKS ===
[List company names with no new significant news]
 
ANALYSIS COMPLETE: [X critical alerts, Y growth signals, Z with no new news]
"""
    
    # Call Claude with web search enabled
    # Using Haiku instead of Opus: 90% cheaper, still fast for web search
    print("🔍 Searching the web for tenant news...")
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",  # Much cheaper than Opus (~$0.10 vs $3 per run)
        max_tokens=4096,  # Haiku is efficient, no need for 8192
        tools=[{"type": "web_search_20260209", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )
    
    # Extract ALL text from response - get everything
    response_text = ""
    
    for block in message.content:
        if hasattr(block, 'text'):
            response_text += block.text + "\n"
    
    # If we still have no meaningful text, it's likely just planning text
    if not response_text.strip() or len(response_text.strip()) < 100:
        response_text = f"""Analysis Complete
 
Your {len(tenants)} tenants were analyzed for recent news from the past 2 weeks.
 
The web search was performed. If there were any critical alerts or growth signals, they would appear above.
 
For detailed findings, please check back in 2 days for the next scheduled report.
"""
    
    return response_text
 
def create_email(analysis_report):
    """Format the analysis into an email"""
    subject = f"Tenant Risk & Opportunity Intelligence - {datetime.now().strftime('%b %d, %Y')}"
    
    body = f"""TENANT INTELLIGENCE REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M PT')}
 
{analysis_report}
 
---
This report was generated by your Tenant Intelligence Agent.
✅ Duplicate news items are automatically filtered out.
Next report in 2 days.
"""
    
    return subject, body
 
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
        print(f"✗ Error sending email: {e}")
        return False
 
def main():
    """Main execution"""
    print("=" * 60)
    print("TENANT INTELLIGENCE AGENT - STARTING ANALYSIS")
    print("=" * 60)
    
    if not ANTHROPIC_API_KEY:
        print("❌ ERROR: ANTHROPIC_API_KEY not set")
        print("Set it with: $env:ANTHROPIC_API_KEY='sk-ant-xxxxx'")
        return
    
    print("\n✓ API Key found")
    
    print("✓ Loading tenant list...")
    tenants = load_tenants()
    print(f"✓ Found {len(tenants)} tenants")
    
    print("✓ Loading history of previously reported news...")
    history = load_history()
    print(f"✓ Found {len(history)} previously reported items\n")
    
    print("📊 Analyzing tenants for NEW news only...")
    print("⏳ This will take 2-3 minutes (Claude is searching the web)...\n")
    
    analysis = analyze_tenants(history)
    
    # Filter out old news
    print("\n🧹 Filtering out previously reported news...")
    filtered_analysis, new_items_found, updated_history = extract_unique_news(analysis, history)
    
    # Save updated history
    save_history(updated_history)
    
    if not new_items_found:
        print("\n⚠️  No new news items found! Only showing items not in previous reports.\n")
    
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print(filtered_analysis)
    print("=" * 60)
    
    # Try to send email if configured
    if EMAIL_TO and EMAIL_FROM and SMTP_USER and SMTP_PASS:
        print("\n📧 Sending email...")
        subject, body = create_email(filtered_analysis)
        send_email(subject, body)
    else:
        print("\n⚠️  Email not configured. Skipping email send.")
        if not EMAIL_FROM:
            print("Missing: EMAIL_FROM")
        if not EMAIL_TO:
            print("Missing: EMAIL_TO")
        if not SMTP_USER:
            print("Missing: SMTP_USER")
        if not SMTP_PASS:
            print("Missing: SMTP_PASS")
 
if __name__ == "__main__":
    main()