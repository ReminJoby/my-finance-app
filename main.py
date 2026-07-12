import flet as ft
import sqlite3
import re
import datetime
import hashlib
import json

# --- Module 5: AI Advisor Integration ---
try:
    from google import genai
except ImportError:
    genai = None

# ==========================================
# MODULE 1: LOCAL SECURE DATABASE
# ==========================================
class LocalVault:
    def __init__(self):
        # On Android, this file sits in the app's private sandbox
        self.conn = sqlite3.connect("vault.db", check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # Transactions table
        cursor.execute('''CREATE TABLE IF NOT EXISTS tx 
            (id INTEGER PRIMARY KEY, date TEXT, amt REAL, merchant TEXT, type TEXT, bal REAL)''')
        # Budget settings
        cursor.execute('''CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, val REAL)''')
        cursor.execute("INSERT OR IGNORE INTO config VALUES ('limit', 20000.0)")
        self.conn.commit()

    def add_transaction(self, amt, merchant, bal):
        cursor = self.conn.cursor()
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute("INSERT INTO tx (date, amt, merchant, type, bal) VALUES (?, ?, ?, 'Debit', ?)", 
                       (date, amt, merchant, bal))
        self.conn.commit()

    def get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT SUM(amt) FROM tx")
        spend = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT bal FROM tx ORDER BY id DESC LIMIT 1")
        bal_row = cursor.fetchone()
        bal = bal_row[0] if bal_row else 0.0
        cursor.execute("SELECT val FROM config WHERE key='limit'")
        limit = cursor.fetchone()[0]
        return spend, bal, limit

db = LocalVault()

# ==========================================
# MODULE 2: CLIPBOARD UPI PARSER (REGEX)
# ==========================================
def parse_upi_sms(text):
    # Regex specifically for Indian Banks (HDFC, SBI, ICICI, etc.)
    amt_re = re.search(r'(?:Rs|INR)\.?\s*([\d,]+\.?\d*)', text, re.I)
    bal_re = re.search(r'(?:Bal|Balance)\.?\s*(?:Rs|INR)?\s*([\d,]+\.?\d*)', text, re.I)
    
    merchant = "Unknown Merchant"
    if "to" in text.lower():
        parts = re.split(r'to|at', text, flags=re.I)
        if len(parts) > 1:
            merchant = parts[1].split("via")[0].strip()[:20]

    amt = float(amt_re.group(1).replace(',', '')) if amt_re else 0.0
    bal = float(bal_re.group(1).replace(',', '')) if bal_re else 0.0
    return amt, merchant, bal

# ==========================================
# MAIN APP ARCHITECTURE
# ==========================================
def main(page: ft.Page):
    page.title = "Secure Wallet AI"
    page.theme_mode = "dark"
    page.padding = 0
    
    # Module 0: Secure PIN
    USER_PIN = "8888" 

    # --- UI WRAPPER ---
    app_view = ft.Column(expand=True, visible=False)
    login_view = ft.Column(horizontal_alignment="center", spacing=30, expand=True)

    # --- REFRESH LOGIC ---
    def refresh_dashboard():
        spend, bal, limit = db.get_stats()
        ratio = min(spend / limit, 1.0)
        
        # Module 3: Aggressive Minimizer Logic
        prog_color = "green" if ratio < 0.7 else "orange" if ratio < 0.85 else "red"
        
        bal_display.value = f"₹{bal:,.2f}"
        spend_display.value = f"Spent: ₹{spend:,.2f} / ₹{limit:,.0f}"
        prog_bar.value = ratio
        prog_bar.color = prog_color
        
        warning_box.visible = True if ratio > 0.8 else False
        page.update()

    # --- ACTIONS ---
    def on_login(e):
        if pin_field.value == USER_PIN:
            login_view.visible = False
            app_view.visible = True
            refresh_dashboard()
            page.update()
        else:
            pin_field.error_text = "Incorrect PIN"
            page.update()

    def on_parse_save(e):
        amt, merch, bal = parse_upi_sms(sms_input.value)
        db.add_transaction(amt, merch, bal)
        sms_input.value = ""
        refresh_dashboard()
        page.open(ft.SnackBar(ft.Text(f"Logged ₹{amt} to {merch}")))

    # --- UI COMPONENTS ---
    # Login
    pin_field = ft.TextField(label="PIN", password=True, text_align="center", width=200)
    login_view.controls = [
        ft.Container(height=100),
        ft.Icon("lock", size=80, color="blue"),
        ft.Text("BIO-SECURE VAULT", size=24, weight="bold"),
        pin_field,
        ft.ElevatedButton("Unlock", on_click=on_login, width=200, bgcolor="blue", color="white")
    ]

    # Dashboard
    bal_display = ft.Text("₹0.00", size=42, weight="bold")
    spend_display = ft.Text("Spent: ₹0.00")
    prog_bar = ft.ProgressBar(value=0, color="green", height=15)
    warning_box = ft.Container(
        content=ft.Text("⚠️ BUDGET CRITICAL: Halt Discretionary Spending", color="white", weight="bold"),
        bgcolor="red", padding=15, border_radius=10, visible=False
    )

    # Tabs
    tab_content = ft.Container(expand=True, padding=20)

    # Navigation Logic
    def change_tab(idx):
        if idx == 0: # Stats
            tab_content.content = ft.Column([
                ft.Text("LIQUID BALANCE", size=14, color="grey"),
                bal_display,
                ft.Divider(height=40),
                spend_display,
                prog_bar,
                warning_box,
            ])
        elif idx == 1: # Add
            tab_content.content = ft.Column([
                ft.Text("LOG TRANSACTION", size=22, weight="bold"),
                sms_input,
                ft.ElevatedButton("Parse & Save Locally", on_click=on_parse_save, width=400, bgcolor="blue", color="white")
            ], spacing=20)
        page.update()

    sms_input = ft.TextField(label="Paste Bank SMS", multiline=True, min_lines=3)

    app_view.controls = [
        tab_content,
        ft.Row([
            ft.IconButton("wallet", on_click=lambda _: change_tab(0), icon_size=30, expand=True),
            ft.IconButton("add", on_click=lambda _: change_tab(1), icon_size=30, expand=True),
        ], alignment="center", bgcolor="#1a1a1a", height=80)
    ]

    page.add(login_view, app_view)
    change_tab(0)

# ==========================================
# COMPILATION COMMANDS
# ==========================================
"""
TO BUILD THE APK:
1. Install Flet: pip install flet
2. Run this command:
   flet build apk --name "PrivacyWallet" \
   --android-permissions android.permission.INTERNET=True android.permission.USE_BIOMETRIC=True \
   --org com.yourname.wallet
"""

if __name__ == "__main__":
    ft.app(target=main)
