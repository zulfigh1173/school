import streamlit as st
import sqlite3, io
import pandas as pd
from pathlib import Path
from datetime import date, timedelta

# PDF - reportlab
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    HAS_PDF = True
except Exception:
    HAS_PDF = False

st.set_page_config(page_title="School Management - Many Schools FIXED", layout="wide", page_icon="🏫")
# SPEED FIX: analysis is cached 60 sec, PDF builds ONLY on button click, no Super Admin charts
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "schools.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS schools (id INTEGER PRIMARY KEY AUTOINCREMENT, school_name TEXT, login_code TEXT UNIQUE, password TEXT, city TEXT, phone TEXT, plan TEXT DEFAULT 'Standard', monthly_charge INTEGER DEFAULT 2500, expiry_date TEXT, payment_status TEXT DEFAULT 'Paid');
    CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, school_id INTEGER, name TEXT, role TEXT, username TEXT, password TEXT);
    CREATE TABLE IF NOT EXISTS students (id INTEGER PRIMARY KEY AUTOINCREMENT, school_id INTEGER, gr TEXT, name TEXT, father TEXT, surname TEXT, class TEXT, monthly_fee INTEGER);
    CREATE TABLE IF NOT EXISTS fees (id INTEGER PRIMARY KEY AUTOINCREMENT, school_id INTEGER, student_id INTEGER, month TEXT, monthly_fee INTEGER, paid_fee INTEGER, due_fee INTEGER, submit_date TEXT);
    CREATE TABLE IF NOT EXISTS cashbook (id INTEGER PRIMARY KEY AUTOINCREMENT, school_id INTEGER, date TEXT, type TEXT, gross_amount INTEGER, description TEXT);
    CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, school_id INTEGER, date TEXT, category TEXT, amount INTEGER, description TEXT);
    CREATE TABLE IF NOT EXISTS income (id INTEGER PRIMARY KEY AUTOINCREMENT, school_id INTEGER, date TEXT, source TEXT, amount INTEGER, description TEXT);
    """)
    conn.commit()
    # MIGRATION: add gender column to old DBs without losing data
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(students)").fetchall()]
        if "gender" not in cols:
            conn.execute("ALTER TABLE students ADD COLUMN gender TEXT DEFAULT 'Male'")
            conn.commit()
    except Exception:
        pass
    c = conn.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
    if c == 0:
        exp = (date.today()+timedelta(days=30)).isoformat()
        conn.execute("INSERT INTO schools (school_name, login_code, password, city, phone, plan, monthly_charge, expiry_date, payment_status) VALUES (?,?,?,?,?,?,?,?,?)",("Govt School Ratodero","RATO01","1234","Ratodero","03001234567","Standard",2500,exp,"Paid"))
        conn.execute("INSERT INTO schools (school_name, login_code, password, city, phone, plan, monthly_charge, expiry_date, payment_status) VALUES (?,?,?,?,?,?,?,?,?)",("City School Larkana","LARK02","5678","Larkana","03007654321","Basic",1500,exp,"Paid"))
        conn.commit()
        for gr,name,father,surname,cls,fee,gen in [("101","Ali","Ahmed","Ghanghro","5th",2000,"Male"),("102","Sara","Khan","Soomro","5th",2000,"Female"),("103","Ahmed","Ali","Junejo","6th",2500,"Male"),("104","Ayesha","Mohammed","Memon","6th",2500,"Female")]:
            conn.execute("INSERT INTO students (school_id, gr, name, father, surname, class, monthly_fee, gender) VALUES (?,?,?,?,?,?,?,?)",(1,gr,name,father,surname,cls,fee,gen))
        conn.commit()
    conn.close()
init_db()

MONTHS = ["Jan 2026","Feb 2026","Mar 2026","Apr 2026","May 2026","Jun 2026","Jul 2026","Aug 2026","Sep 2026","Oct 2026","Nov 2026","Dec 2026","Jan 2027","Feb 2027","Mar 2027"]
CLASSES = ["1st","2nd","3rd","4th","5th","6th","7th","8th","9th","10th"]

# ---------- SESSION ----------
for k,v in [("logged_in_as",None),("school_id",None),("school_name",""),("expiry","")]:
    if k not in st.session_state: st.session_state[k]=v
def chart_button(key, label="📊 Show Charts"):
    # One easy button per menu - press to show ONLY that menu's charts + detail info
    if st.button(label, key=f"btn_{key}"):
        st.session_state[f"show_{key}"] = not st.session_state.get(f"show_{key}", False)
        st.rerun()
    show = st.session_state.get(f"show_{key}", False)
    if show:
        st.caption("✅ Charts ON - press button again to hide")
    else:
        st.caption("👆 Press 'Show Charts' button above to see charts for this menu only")
    return show

def charts_on():
    return st.session_state.get("global_show_charts", False)

def p_bar(data, x, y, title, color="#1f77b4"):
    """Big clean chart like Easy Charts app - blue bars, value on top, 450px tall"""
    try:
        import plotly.express as px
        fig = px.bar(data, x=x, y=y, title=title, color_discrete_sequence=[color], text=y)
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig.update_layout(height=450, title_font_size=22, title_x=0.5, xaxis_title="", yaxis_title="", showlegend=False, plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=60, b=60, l=40, r=20))
        fig.update_xaxes(tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"Chart: {title} - {e}")

def p_pie(labels, values, title, colors=None):
    """Big pie like Pass vs Fail - green/red style, % shown"""
    try:
        import plotly.express as px
        import pandas as _pd
        _df = _pd.DataFrame({"label": labels, "value": values})
        fig = px.pie(_df, names="label", values="value", title=title, color_discrete_sequence=colors or ["#2ca02c","#d62728","#1f77b4","#ff7f0e","#9467bd"])
        fig.update_traces(textinfo="percent+label", textfont_size=16)
        fig.update_layout(height=450, title_font_size=22, title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"Pie: {title} - {e}")

def p_line(data, x, y_list, title):
    """Big line chart like timeline"""
    try:
        import plotly.express as px
        fig = px.line(data, x=x, y=y_list, title=title, markers=True)
        fig.update_layout(height=450, title_font_size=22, title_x=0.5, plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"Line: {title} - {e}")

def chart_detail(title, detail):
    st.markdown(f"**{title}**")
    st.info(f"📖 Detail: {detail}")

def clear_cache():
    try: get_analysis_cached.clear()
    except Exception: pass

def logout():
    st.session_state.logged_in_as=None; st.session_state.school_id=None; st.session_state.school_name=""; st.session_state.expiry=""; st.rerun()

# ---------- PDF GENERATOR ----------
@st.cache_data(ttl=10, show_spinner=False)
def get_analysis_cached(school_id, _db_mtime=0):
    # _db_mtime forces refresh when DB file changes - fixes Rs.0 stuck bug
    """Detailed analysis for every section - returns dict of DataFrames + insights."""
    conn=get_conn()
    students=pd.read_sql("SELECT * FROM students WHERE school_id=?", conn, params=(school_id,))
    fees=pd.read_sql("SELECT * FROM fees WHERE school_id=?", conn, params=(school_id,))
    cash=pd.read_sql("SELECT * FROM cashbook WHERE school_id=?", conn, params=(school_id,))
    exp=pd.read_sql("SELECT * FROM expenses WHERE school_id=?", conn, params=(school_id,))
    inc=pd.read_sql("SELECT * FROM income WHERE school_id=?", conn, params=(school_id,))
    users=pd.read_sql("SELECT * FROM users WHERE school_id=?", conn, params=(school_id,))
    conn.close()
    a={}
    a['students']=students; a['fees']=fees; a['cash']=cash; a['expenses']=exp; a['income']=inc; a['users']=users
    # Students analysis
    if not students.empty:
        a['by_class']=students.groupby("class").agg(total_students=("id","count"), total_expected_fee=("monthly_fee","sum"), avg_fee=("monthly_fee","mean")).reset_index().sort_values("class")
        a['by_surname']=students.groupby("surname").size().reset_index(name="count").sort_values("count", ascending=False) if "surname" in students else pd.DataFrame()
        # Gender analysis
        if "gender" in students.columns:
            a['by_gender']=students.groupby("gender").agg(count=("id","count"), total_fee=("monthly_fee","sum"), avg_fee=("monthly_fee","mean")).reset_index()
            a['male_count']=int((students["gender"]=="Male").sum()); a['female_count']=int((students["gender"]=="Female").sum())
        else:
            a['by_gender']=pd.DataFrame(); a['male_count']=0; a['female_count']=0
    else:
        a['by_class']=pd.DataFrame(); a['by_surname']=pd.DataFrame(); a['by_gender']=pd.DataFrame(); a['male_count']=0; a['female_count']=0
    # Fees analysis
    if not fees.empty:
        a['fees_by_month']=fees.groupby("month").agg(records=("id","count"), expected=("monthly_fee","sum"), paid=("paid_fee","sum"), due=("due_fee","sum")).reset_index()
        a['fees_by_month']["collection_rate_%"]=(a['fees_by_month']["paid"]/a['fees_by_month']["expected"]*100).round(1)
        a['total_expected']=int(fees["monthly_fee"].sum()); a['total_paid']=int(fees["paid_fee"].sum()); a['total_due']=int(fees["due_fee"].sum())
        a['collection_rate']=round(a['total_paid']/a['total_expected']*100,1) if a['total_expected'] else 0
        a['avg_paid']=round(fees["paid_fee"].mean(),1); a['fully_paid']=int((fees["due_fee"]==0).sum()); a['partial']=int((fees["due_fee"]>0).sum())
    else:
        a['fees_by_month']=pd.DataFrame(); a['total_expected']=0; a['total_paid']=0; a['total_due']=0; a['collection_rate']=0; a['avg_paid']=0; a['fully_paid']=0; a['partial']=0
    # Defaulter analysis - current month Nov 2026 default
    if not students.empty:
        paid_ids=set(fees[fees["month"]=="Nov 2026"]["student_id"].tolist()) if not fees.empty else set()
        # Use last month with fees if Nov empty
        if not fees.empty and len(paid_ids)==0:
            last_month=fees.sort_values("id").iloc[-1]["month"]; paid_ids=set(fees[fees["month"]==last_month]["student_id"].tolist()); a['defaulter_month']=last_month
        else: a['defaulter_month']="Nov 2026"
        a['defaulter_count']=len(students)-len(paid_ids)
        a['defaulter_expected']=int(students[~students["id"].isin(paid_ids)]["monthly_fee"].sum()) if a['defaulter_count'] else 0
    else:
        a['defaulter_count']=0; a['defaulter_expected']=0; a['defaulter_month']="Nov 2026"
    # Cashbook analysis
    if not cash.empty:
        a['cash_by_date']=cash.groupby(["date","type"])["gross_amount"].sum().unstack(fill_value=0).reset_index()
        a['cash_by_type']=cash.groupby("type")["gross_amount"].sum()
        a['total_income_cash']=int(a['cash_by_type'].get("income",0)); a['total_exp_cash']=int(a['cash_by_type'].get("expense",0)); a['cash_in_hand']=a['total_income_cash']-a['total_exp_cash']
        a['avg_daily_income']=round(cash[cash["type"]=="income"].groupby("date")["gross_amount"].sum().mean(),1) if (cash["type"]=="income").any() else 0
        a['avg_daily_expense']=round(cash[cash["type"]=="expense"].groupby("date")["gross_amount"].sum().mean(),1) if (cash["type"]=="expense").any() else 0
        a['best_income_day']=cash[cash["type"]=="income"].groupby("date")["gross_amount"].sum().idxmax() if (cash["type"]=="income").any() else "-"
        a['best_expense_day']=cash[cash["type"]=="expense"].groupby("date")["gross_amount"].sum().idxmax() if (cash["type"]=="expense").any() else "-"
    else:
        a['cash_by_date']=pd.DataFrame(); a['total_income_cash']=0; a['total_exp_cash']=0; a['cash_in_hand']=0; a['avg_daily_income']=0; a['avg_daily_expense']=0; a['best_income_day']="-"; a['best_expense_day']="-"
    # Expenses analysis
    if not exp.empty:
        a['exp_by_cat']=exp.groupby("category").agg(count=("id","count"), total=("amount","sum"), avg=("amount","mean")).reset_index().sort_values("total", ascending=False)
        a['exp_by_date']=exp.groupby("date")["amount"].sum().reset_index()
        a['top_expense_cat']=a['exp_by_cat'].iloc[0]["category"] if not a['exp_by_cat'].empty else "-"
        a['top_expense_amt']=int(a['exp_by_cat'].iloc[0]["total"]) if not a['exp_by_cat'].empty else 0
    else:
        a['exp_by_cat']=pd.DataFrame(); a['exp_by_date']=pd.DataFrame(); a['top_expense_cat']="-"; a['top_expense_amt']=0
    # Income analysis
    if not inc.empty:
        a['inc_by_src']=inc.groupby("source").agg(count=("id","count"), total=("amount","sum"), avg=("amount","mean")).reset_index().sort_values("total", ascending=False)
        a['top_income_src']=a['inc_by_src'].iloc[0]["source"] if not a['inc_by_src'].empty else "-"
    else:
        a['inc_by_src']=pd.DataFrame(); a['top_income_src']="-"
    # Users analysis
    if not users.empty:
        a['users_by_role']=users.groupby("role").size().reset_index(name="count")
    else: a['users_by_role']=pd.DataFrame()
    return a

def insights_text(a):
    lines=[]
    lines.append(f"Gender: Male {a.get('male_count',0)} | Female {a.get('female_count',0)}. ")
    lines.append(f"Total Students: {len(a['students'])}. " + (f"Highest students in class {a['by_class'].sort_values('total_students',ascending=False).iloc[0]['class']} ({int(a['by_class'].sort_values('total_students',ascending=False).iloc[0]['total_students'])} students)." if not a['by_class'].empty else "No students yet."))
    lines.append(f"Fees: Expected Rs.{a['total_expected']}, Collected Rs.{a['total_paid']}, Due Rs.{a['total_due']}. Collection Rate {a['collection_rate']}%. Fully Paid records {a['fully_paid']}, Partial {a['partial']}.")
    if not a['fees_by_month'].empty:
        best=a['fees_by_month'].sort_values("paid",ascending=False).iloc[0]; worst=a['fees_by_month'].sort_values("paid").iloc[0]
        lines.append(f"Best fee month: {best['month']} (Rs.{int(best['paid'])}). Lowest fee month: {worst['month']} (Rs.{int(worst['paid'])}). Focus recovery in lowest month.")
    lines.append(f"Defaulters ({a['defaulter_month']}): {a['defaulter_count']} students, Expected Due Rs.{a['defaulter_expected']}.")
    lines.append(f"Cashbook: Total Income Rs.{a['total_income_cash']}, Total Expense Rs.{a['total_exp_cash']}, Cash in Hand Rs.{a['cash_in_hand']}. Avg Daily Income Rs.{a['avg_daily_income']}, Avg Daily Expense Rs.{a['avg_daily_expense']}. Best Income Day {a['best_income_day']}, Highest Expense Day {a['best_expense_day']}.")
    lines.append(f"Expenses: Top category {a['top_expense_cat']} Rs.{a['top_expense_amt']}. Control this category first to save cash.")
    lines.append(f"Other Income: Top source {a['top_income_src']}.")
    lines.append(f"Staff Users: {len(a['users'])} users.")
    if a['cash_in_hand']<0: lines.append("WARNING: Cash in Hand is NEGATIVE - expenses are more than income. Cut expenses immediately.")
    elif a['collection_rate']<70 and a['total_expected']>0: lines.append("ACTION: Collection rate below 70% - send defaulter reminders this week.")
    else: lines.append("Overall: School is in stable position. Keep collecting fees on time.")
    return lines

def make_pdf(school_name, school_id, month_filter="All"):
    # Kept for old calls - now redirects to full analysis PDF
    return make_analysis_pdf(school_name, school_id)

def make_analysis_pdf(school_name, school_id):
    if not HAS_PDF: return None
    a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
    buf=io.BytesIO(); styles=getSampleStyleSheet()
    doc=SimpleDocTemplate(buf, pagesize=A4, topMargin=12*mm, bottomMargin=12*mm)
    story=[]
    def H(txt, lvl='Heading1'):
        story.append(Paragraph(f"<b>{txt}</b>", styles[lvl])); story.append(Spacer(1,2*mm))
    def P(txt): story.append(Paragraph(txt, styles['Normal'])); story.append(Spacer(1,2*mm))
    def table_from_df(df, cols=None):
        if df is None or df.empty: P("No data yet."); return
        if cols: df=df[cols]
        data=[[str(c) for c in df.columns]]+[[str(v) for v in row] for row in df.values.tolist()]
        t=Table(data, repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1f4e79')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),0.5,colors.grey),('FONTSIZE',(0,0),(-1,-1),8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#eaf1f8')])]))
        story.append(t); story.append(Spacer(1,4*mm))
    H(f"{school_name} - COMPLETE DATA ANALYSIS", 'Title')
    P(f"Date: {date.today()} | All Sections Analysis | Auto-Generated Insights Included")
    H("1. Executive Summary - Key Insights")
    for line in insights_text(a): P(f"- {line}")
    H("2. Students Analysis - Detailed")
    P(f"Gender: Male {a.get('male_count',0)} | Female {a.get('female_count',0)} | ")
    P(f"Total Students: {len(a['students'])} | Total Expected Monthly Fee: Rs. {int(a['students']['monthly_fee'].sum()) if not a['students'].empty else 0} | Avg Fee: Rs. {round(a['students']['monthly_fee'].mean(),1) if not a['students'].empty else 0} | Min Fee: Rs. {int(a['students']['monthly_fee'].min()) if not a['students'].empty else 0} | Max Fee: Rs. {int(a['students']['monthly_fee'].max()) if not a['students'].empty else 0}")
    P("Class-wise Breakdown:"); table_from_df(a['by_class'])
    P("Gender-wise: Male / Female"); table_from_df(a['by_gender'])
    P("Surname-wise Count:"); table_from_df(a['by_surname'])
    H("3. Fees Analysis - Detailed")
    P(f"Total Expected Rs.{a['total_expected']} | Collected Rs.{a['total_paid']} | Due Rs.{a['total_due']} | Collection Rate {a['collection_rate']}% | Avg Paid Rs.{a['avg_paid']} | Fully Paid {a['fully_paid']} | Partial {a['partial']}")
    P("Month-wise Fees:"); table_from_df(a['fees_by_month'])
    H("4. Defaulter Analysis")
    P(f"Defaulter Month: {a['defaulter_month']} | Defaulters: {a['defaulter_count']} | Expected Due from Defaulters: Rs.{a['defaulter_expected']}")
    H("5. Cashbook Analysis - Detailed")
    P(f"Total Income Rs.{a['total_income_cash']} | Total Expense Rs.{a['total_exp_cash']} | Cash in Hand Rs.{a['cash_in_hand']} | Avg Daily Income Rs.{a['avg_daily_income']} | Avg Daily Expense Rs.{a['avg_daily_expense']} | Best Income Day {a['best_income_day']} | Highest Expense Day {a['best_expense_day']}")
    P("Cashbook by Date:"); table_from_df(a['cash_by_date'])
    H("6. Expenses Analysis - Detailed")
    P(f"Total Expenses: Rs. {int(a['expenses']['amount'].sum()) if not a['expenses'].empty else 0} | Records: {len(a['expenses'])} | Avg Expense: Rs. {round(a['expenses']['amount'].mean(),1) if not a['expenses'].empty else 0} | Top Category: {a['top_expense_cat']} Rs.{a['top_expense_amt']}")
    P("Category-wise Expenses:"); table_from_df(a['exp_by_cat'])
    H("7. Other Income Analysis - Detailed")
    P(f"Total Other Income: Rs. {int(a['income']['amount'].sum()) if not a['income'].empty else 0} | Records: {len(a['income'])} | Top Source: {a['top_income_src']}")
    P("Source-wise Income:"); table_from_df(a['inc_by_src'])
    H("8. Users / Staff Analysis")
    P(f"Total Staff Users: {len(a['users'])}"); table_from_df(a['users_by_role'])
    H("9. Final Recommendations")
    for line in insights_text(a): P(f"- {line}")
    doc.build(story); buf.seek(0); return buf.getvalue()

def crud_table(df, table, id_col="id", school_filter=True):
    """Generic Edit/Delete UI. df must contain id column."""
    if df.empty:
        st.info("No records yet."); return
    st.dataframe(df.drop(columns=["id"], errors="ignore"), width="stretch")
    st.markdown("#### ✏️ Edit / 🗑️ Delete")
    # label
    labels=[]
    # FIX: use dict records, NOT itertuples().class - 'class' is a Python keyword and crashes
    for r in df.to_dict("records"):
        vals=[str(r.get(c,"")) for c in df.columns if c!="id"][:3]
        labels.append(f"ID {r.get('id')} | {' - '.join(vals)}")
    sel = st.selectbox("Select Record to Edit / Delete", labels, key=f"sel_{table}")
    sel_id = int(sel.split("|")[0].replace("ID","").strip())
    row = df[df["id"]==sel_id].iloc[0]
    c1,c2 = st.columns(2)
    with c1:
        if st.button(f"✏️ Edit Selected - {table}", key=f"edit_{table}"):
            st.session_state[f"editing_{table}"] = sel_id
            st.rerun()
    with c2:
        if st.button(f"🗑️ Delete Selected - {table}", key=f"del_{table}"):
            conn=get_conn(); conn.execute(f"DELETE FROM {table} WHERE id=?", (sel_id,)); conn.commit(); conn.close()
            st.success("Deleted!"); st.rerun()
    return sel_id

# ---------- LOGIN ----------
if st.session_state.logged_in_as is None:
    st.title("🏫 School Management - Many Schools ✅ FIXED VERSION")
    st.markdown("One App - All Schools | Students + Fees + Cashbook + Defaulter | CRUD + Charts + PDF")
    tab1, tab2 = st.tabs(["🏫 School Login", "👑 Super Admin Login"])
    with tab1:
        code = st.text_input("School Code (e.g. RATO01)", key="code")
        pwd = st.text_input("Password", type="password", key="pwd")
        if st.button("Login as School", width="stretch"):
            conn=get_conn(); row=conn.execute("SELECT * FROM schools WHERE login_code=? AND password=?", (code.strip().upper(), pwd.strip())).fetchone(); conn.close()
            if row:
                try: exp=date.fromisoformat(row["expiry_date"]) if row["expiry_date"] else date.today()+timedelta(days=30)
                except Exception: exp=date.today()+timedelta(days=30)
                if date.today()>exp: st.error(f"❌ Plan Expired on {exp}. Pay Rs. {row['monthly_charge']}. JazzCash: 0300-1234567")
                else:
                    st.session_state.logged_in_as="school"; st.session_state.school_id=row["id"]; st.session_state.school_name=row["school_name"]; st.session_state.expiry=row["expiry_date"]; st.rerun()
            else: st.error(f"Wrong. You typed Code='{code.strip().upper()}' - Try RATO01 / 1234")
        st.info("Demo: **RATO01 / 1234** | **LARK02 / 5678**")
    with tab2:
        u=st.text_input("Admin Username", key="au"); p=st.text_input("Admin Password", type="password", key="ap")
        st.caption(f"Typed: '{u.strip()}' | Password length: {len(p.strip())}")
        if st.button("Login as Super Admin", width="stretch"):
            if u.strip().lower()=="admin" and p.strip()=="admin123":
                st.session_state.logged_in_as="super"; st.rerun()
            else: st.error("Wrong! type by hand, no autofill.")
        if st.button("Clear / Try Again"):
            st.session_state.logged_in_as=None; st.rerun()
    st.stop()

# ---------- SUPER ADMIN ----------
if st.session_state.logged_in_as=="super":
    st.title("👑 Super Admin - Manage Schools")
    if st.button("🔄 Refresh Data"): clear_cache(); st.rerun()
    if st.button("Logout"): logout()
    st.subheader("➕ Add New School")
    with st.form("new_school"):
        c1,c2,c3=st.columns(3)
        with c1: sname=st.text_input("School Name")
        with c2: scode=st.text_input("Login Code (e.g. CITY04)")
        with c3: spass=st.text_input("Password", value="1234")
        c4,c5,c6=st.columns(3)
        with c4: city=st.text_input("City")
        with c5: phone=st.text_input("Phone")
        with c6: plan=st.selectbox("Plan", ["Basic","Standard","Premium"])
        charge={"Basic":1500,"Standard":2500,"Premium":4000}[plan]
        exp_days=st.number_input("Trial / Plan Days", value=30)
        if st.form_submit_button("Create School"):
            if sname and scode:
                conn=get_conn()
                try:
                    exp=(date.today()+timedelta(days=int(exp_days))).isoformat()
                    conn.execute("INSERT INTO schools (school_name, login_code, password, city, phone, plan, monthly_charge, expiry_date, payment_status) VALUES (?,?,?,?,?,?,?,?,?)",(sname,scode.strip().upper(),spass.strip(),city,phone,plan,charge,exp,"Paid"))
                    conn.commit(); st.success(f"Created! Code: {scode.strip().upper()} Pass: {spass} Charge: Rs.{charge}")
                except Exception as e: st.error(f"Code exists! {e}")
                conn.close()
    st.subheader("🏫 All Schools - CRUD (Edit / Delete / Change Password)")
    conn=get_conn()
    df=pd.read_sql("SELECT * FROM schools ORDER BY id", conn)
    counts=[conn.execute("SELECT COUNT(*) FROM students WHERE school_id=?", (int(s),)).fetchone()[0] for s in df["id"]] if not df.empty else []
    conn.close()
    if not df.empty: df["total_students"]=counts
    st.dataframe(df, width="stretch")
    if not df.empty:
        # Edit school
        st.markdown("#### ✏️ Edit School / 🔑 Change School Password")
        labels=[f"ID {r.id} | {r.school_name} ({r.login_code})" for r in df.itertuples()]
        sel=st.selectbox("Select School", labels, key="super_school_sel")
        sid=int(sel.split("|")[0].replace("ID","").strip())
        srow=df[df["id"]==sid].iloc[0]
        with st.form("edit_school"):
            e1,e2,e3=st.columns(3)
            with e1: ename=st.text_input("School Name", value=srow["school_name"]); ecode=st.text_input("Login Code", value=srow["login_code"])
            with e2: ecity=st.text_input("City", value=str(srow["city"] or "")); ephone=st.text_input("Phone", value=str(srow["phone"] or ""))
            with e3: eplan=st.selectbox("Plan", ["Basic","Standard","Premium"], index=["Basic","Standard","Premium"].index(srow["plan"] or "Standard")); echarge=st.number_input("Monthly Charge", value=int(srow["monthly_charge"] or 2500))
            estatus=st.selectbox("Payment Status", ["Paid","Unpaid"], index=0 if srow["payment_status"]=="Paid" else 1)
            eexp=st.text_input("Expiry Date (YYYY-MM-DD)", value=str(srow["expiry_date"] or ""))
            if st.form_submit_button("💾 Save School Changes"):
                conn=get_conn(); conn.execute("UPDATE schools SET school_name=?, login_code=?, city=?, phone=?, plan=?, monthly_charge=?, payment_status=?, expiry_date=? WHERE id=?", (ename,ecode.strip().upper(),ecity,ephone,eplan,echarge,estatus,eexp,sid)); conn.commit(); conn.close(); st.success("School Updated!"); st.rerun()
        with st.form("change_school_pass"):
            npass=st.text_input("New Password for this School", type="password")
            if st.form_submit_button("🔑 Change School Password"):
                if npass:
                    conn=get_conn(); conn.execute("UPDATE schools SET password=? WHERE id=?", (npass.strip(),sid)); conn.commit(); conn.close(); st.success(f"Password changed for {srow['school_name']} - New: {npass}"); st.rerun()
                else: st.error("Enter new password")
        cdel1,cdel2=st.columns(2)
        with cdel1:
            if st.button("Extend 30 Days + Mark Paid"):
                conn=get_conn(); row=conn.execute("SELECT expiry_date FROM schools WHERE id=?", (sid,)).fetchone()
                try: old=date.fromisoformat(row[0])
                except Exception: old=date.today()
                new=max(old,date.today())+timedelta(days=30)
                conn.execute("UPDATE schools SET expiry_date=?, payment_status='Paid' WHERE id=?", (new.isoformat(),sid)); conn.commit(); conn.close(); st.success(f"Extended to {new}"); st.rerun()
        with cdel2:
            if st.button("🗑️ Delete This School ( + its data )"):
                conn=get_conn()
                for tb in ["students","fees","cashbook","expenses","income","users"]:
                    conn.execute(f"DELETE FROM {tb} WHERE school_id=?", (sid,))
                conn.execute("DELETE FROM schools WHERE id=?", (sid,)); conn.commit(); conn.close(); st.success("School Deleted"); st.rerun()
    # SUPER ADMIN: NO CHARTS HERE - Charts are ONLY inside each School's own data
    # Super Admin sees only Tables + CRUD + Extend/Delete, as you asked.
    st.caption("ℹ️ Charts are not shown in Super Admin. Open any School login to see that school's charts according to its own data.")
    st.stop()

# ---------- SCHOOL APP ----------
school_id=st.session_state.school_id; school_name=st.session_state.school_name
with st.sidebar:
    st.title(f"🏫 {school_name}")
    st.caption(f"Expiry: {st.session_state.get('expiry')}")
    menu=st.radio("Menu", ["📊 Dashboard","👨🎓 Students","💰 Collect Fee","🚨 Defaulter List","📒 Cashbook","💸 Expenses","💵 Income","🔑 Change Password","📄 Reports / PDF"])
    st.caption("✅ No Users menu in School login. No Timeline menu - Slicer + Timeline are only in left sidebar below.")
    st.divider()
    st.markdown("### 📊 Charts Control")
    # ONE easy button - press in any menu, charts for THAT menu will show. Press again to hide.
    if st.button("📊 Show Charts for This Menu", key="sidebar_show_charts", width="stretch"):
        st.session_state["global_show_charts"] = True
    if st.button("🙈 Hide Charts", key="sidebar_hide_charts", width="stretch"):
        st.session_state["global_show_charts"] = False
    if st.session_state.get("global_show_charts"):
        st.success("✅ Charts ON for this menu")
    else:
        st.caption("Charts are OFF. Press 'Show Charts' to see charts + detail info for this menu only.")
    st.divider()
    st.markdown("### 🎚️ Slicer + Timeline - Left Only (No Menu)")
    st.caption("⏱️ Timeline = From Date → To Date below. Change dates to see that period in Dashboard / Cashbook.")
    st.caption("These slicers filter Students, Fees, Cashbook & Timeline everywhere below.")
    st.session_state["slice_gender"] = st.multiselect("👦👧 Gender Slicer", ["Male","Female"], default=st.session_state.get("slice_gender", ["Male","Female"]), key="sl_gender")
    st.session_state["slice_class"] = st.multiselect("🏫 Class Slicer", CLASSES, default=st.session_state.get("slice_class", CLASSES), key="sl_class")
    st.session_state["slice_fee_min"], st.session_state["slice_fee_max"] = st.slider("💰 Monthly Fee Range (Rs.)", 0, 10000, (st.session_state.get("slice_fee_min",0), st.session_state.get("slice_fee_max",10000)), step=500, key="sl_fee")
    _d1,_d2 = st.columns(2)
    with _d1: st.session_state["slice_from"] = st.date_input("📅 From Date", value=st.session_state.get("slice_from", __import__("datetime").date(2025,1,1)), key="sl_from")
    with _d2: st.session_state["slice_to"] = st.date_input("📅 To Date", value=st.session_state.get("slice_to", __import__("datetime").date.today()), key="sl_to")
    st.markdown("**⏱️ Timeline Slider**")
    st.caption("Use From / To dates above as Timeline. Dashboard + Cashbook follow these dates.")
    if st.button("🔄 Reset Slicers", key="reset_slicers"):
        st.session_state["slice_gender"]=["Male","Female"]; st.session_state["slice_class"]=CLASSES; st.session_state["slice_fee_min"]=0; st.session_state["slice_fee_max"]=10000; st.rerun()
    st.caption(f"Active: Gender {len(st.session_state.get('slice_gender',[]))} | Class {len(st.session_state.get('slice_class',[]))} | Fee {st.session_state.get('slice_fee_min',0)}-{st.session_state.get('slice_fee_max',10000)}")
    if st.button("🔄 Refresh Data"): clear_cache(); st.rerun()
    if st.button("Logout"): logout()

conn=get_conn()
total_students=conn.execute("SELECT COUNT(*) FROM students WHERE school_id=?", (school_id,)).fetchone()[0]
total_fees=conn.execute("SELECT IFNULL(SUM(paid_fee),0) FROM fees WHERE school_id=?", (school_id,)).fetchone()[0]
total_income=conn.execute("SELECT IFNULL(SUM(gross_amount),0) FROM cashbook WHERE school_id=? AND type='income'", (school_id,)).fetchone()[0]
total_expense=conn.execute("SELECT IFNULL(SUM(gross_amount),0) FROM cashbook WHERE school_id=? AND type='expense'", (school_id,)).fetchone()[0]
cash_in_hand=total_income-total_expense
today_str=date.today().isoformat()
today_income=conn.execute("SELECT IFNULL(SUM(gross_amount),0) FROM cashbook WHERE school_id=? AND date=? AND type='income'", (school_id,today_str)).fetchone()[0]
today_expense=conn.execute("SELECT IFNULL(SUM(gross_amount),0) FROM cashbook WHERE school_id=? AND date=? AND type='expense'", (school_id,today_str)).fetchone()[0]
conn.close()

# ---------- TOP TOTALS - Box Style, Section-wise ----------
def _box(label, value, color, emoji=""):
    return f"""<div style="background:{color}; border-radius:12px; padding:14px 10px; text-align:center; border:1px solid #ddd; box-shadow:0 2px 6px rgba(0,0,0,0.08); min-height:92px;">
<div style="font-size:22px;">{emoji}</div>
<div style="font-size:12px; color:#555; font-weight:600; margin:2px 0;">{label}</div>
<div style="font-size:19px; font-weight:800; color:#111;">{value}</div>
</div>"""

def show_boxes(items):
    # items = list of (label, value, color, emoji) - show 4 per row, box style
    for i in range(0, len(items), 4):
        if i > 0:
            # NEW LINE + SPACE before 2nd row - Total Income (Timeline) row starts on new line with gap
            st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        row = items[i:i+4]
        cols = st.columns(len(row), gap="large")  # NEW SPACE between boxes
        for col, (label, value, color, emoji) in zip(cols, row):
            with col:
                st.markdown(_box(label, value, color, emoji), unsafe_allow_html=True)
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)  # NEW SPACE after boxes

def show_top_totals(section="dashboard"):
    """Dashboard = ALL boxes. Other sections = ONLY that section's related boxes."""
    conn = get_conn()
    try:
        # Common numbers
        male = conn.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND gender='Male'", (school_id,)).fetchone()[0]
        female = conn.execute("SELECT COUNT(*) FROM students WHERE school_id=? AND gender='Female'", (school_id,)).fetchone()[0]
        exp_fee = conn.execute("SELECT IFNULL(SUM(monthly_fee),0) FROM students WHERE school_id=?", (school_id,)).fetchone()[0]
        nclass = conn.execute("SELECT COUNT(DISTINCT class) FROM students WHERE school_id=?", (school_id,)).fetchone()[0]
        avg_fee = conn.execute("SELECT IFNULL(AVG(monthly_fee),0) FROM students WHERE school_id=?", (school_id,)).fetchone()[0]
        total_paid = conn.execute("SELECT IFNULL(SUM(paid_fee),0) FROM fees WHERE school_id=?", (school_id,)).fetchone()[0]
        total_due = conn.execute("SELECT IFNULL(SUM(due_fee),0) FROM fees WHERE school_id=?", (school_id,)).fetchone()[0]
        coll = round((total_paid/(exp_fee) * 100) if exp_fee else 0, 1)
        # Defaulter for current month (Nov = MONTHS[10])
        cur_month = MONTHS[10] if len(MONTHS)>10 else MONTHS[-1]
        def_count = conn.execute("SELECT COUNT(*) FROM students s LEFT JOIN fees f ON s.id=f.student_id AND f.month=? AND f.school_id=? WHERE s.school_id=? AND (f.id IS NULL OR f.due_fee>0)", (cur_month, school_id, school_id)).fetchone()[0]
        def_due = conn.execute("SELECT IFNULL(SUM(s.monthly_fee - IFNULL(f.paid_fee,0)),0) FROM students s LEFT JOIN fees f ON s.id=f.student_id AND f.month=? AND f.school_id=? WHERE s.school_id=? AND (f.id IS NULL OR f.due_fee>0)", (cur_month, school_id, school_id)).fetchone()[0]
        exp_total = conn.execute("SELECT IFNULL(SUM(amount),0) FROM expenses WHERE school_id=?", (school_id,)).fetchone()[0]
        exp_today = conn.execute("SELECT IFNULL(SUM(amount),0) FROM expenses WHERE school_id=? AND date=?", (school_id, today_str)).fetchone()[0]
        top_cat_row = conn.execute("SELECT category, IFNULL(SUM(amount),0) as tot FROM expenses WHERE school_id=? GROUP BY category ORDER BY tot DESC LIMIT 1", (school_id,)).fetchone()
        top_cat = f"{top_cat_row[0]} (Rs. {int(top_cat_row[1]):,})" if top_cat_row else "-"
        inc_total = conn.execute("SELECT IFNULL(SUM(amount),0) FROM income WHERE school_id=?", (school_id,)).fetchone()[0]
        inc_today = conn.execute("SELECT IFNULL(SUM(amount),0) FROM income WHERE school_id=? AND date=?", (school_id, today_str)).fetchone()[0]
        top_src_row = conn.execute("SELECT source, IFNULL(SUM(amount),0) as tot FROM income WHERE school_id=? GROUP BY source ORDER BY tot DESC LIMIT 1", (school_id,)).fetchone()
        top_src = f"{top_src_row[0]} (Rs. {int(top_src_row[1]):,})" if top_src_row else "-"
    except Exception as e:
        male=female=exp_fee=nclass=avg_fee=total_paid=total_due=coll=def_count=def_due=exp_total=exp_today=inc_total=inc_today=0
        top_cat=top_src="-"
    finally:
        conn.close()

    # MENU-DEPENDENT: boxes follow LEFT SIDEBAR slicers (Gender / Class / Fee / Date)
    _sg = st.session_state.get("slice_gender", ["Male","Female"]) or ["Male","Female"]
    _sc = st.session_state.get("slice_class", CLASSES) or CLASSES
    _fmin = st.session_state.get("slice_fee_min", 0); _fmax = st.session_state.get("slice_fee_max", 10000)
    _from = str(st.session_state.get("slice_from", "2025-01-01")); _to = str(st.session_state.get("slice_to", today_str))
    _g_ph = ",".join([f"'{g}'" for g in _sg]); _c_ph = ",".join([f"'{c}'" for c in _sc])
    st.caption(f"🎚️ Boxes are Menu-Dependent | Slicer: Gender {_sg} | Class {_sc} | Fee Rs.{_fmin}-{_fmax} | Timeline {_from} to {_to}  —  Change slicer in left sidebar, boxes change instantly.")
    # Re-compute menu-dependent numbers with slicers
    try:
        conn2 = get_conn()
        # Students filtered by slicer
        _stu = conn2.execute(f"SELECT COUNT(*), IFNULL(SUM(monthly_fee),0), IFNULL(AVG(monthly_fee),0), COUNT(DISTINCT class) FROM students WHERE school_id=? AND gender IN ({_g_ph}) AND class IN ({_c_ph}) AND monthly_fee BETWEEN ? AND ?", (school_id, _fmin, _fmax)).fetchone()
        total_students_f, exp_fee_f, avg_fee_f, nclass_f = int(_stu[0]), int(_stu[1]), int(_stu[2]), int(_stu[3])
        male_f = conn2.execute(f"SELECT COUNT(*) FROM students WHERE school_id=? AND gender='Male' AND class IN ({_c_ph}) AND monthly_fee BETWEEN ? AND ?", (school_id, _fmin, _fmax)).fetchone()[0]
        female_f = conn2.execute(f"SELECT COUNT(*) FROM students WHERE school_id=? AND gender='Female' AND class IN ({_c_ph}) AND monthly_fee BETWEEN ? AND ?", (school_id, _fmin, _fmax)).fetchone()[0]
        # Fees: only students matching slicer + date range
        _fee = conn2.execute(f"SELECT IFNULL(SUM(f.paid_fee),0), IFNULL(SUM(f.due_fee),0) FROM fees f JOIN students s ON f.student_id=s.id WHERE f.school_id=? AND s.gender IN ({_g_ph}) AND s.class IN ({_c_ph}) AND f.submit_date BETWEEN ? AND ?", (school_id, _from, _to)).fetchone()
        total_paid_f, total_due_f = int(_fee[0]), int(_fee[1])
        coll_f = round((total_paid_f/exp_fee_f*100) if exp_fee_f else 0, 1)
        # Cashbook filtered by timeline dates
        _cash = conn2.execute("SELECT IFNULL(SUM(CASE WHEN type='income' THEN gross_amount ELSE 0 END),0), IFNULL(SUM(CASE WHEN type='expense' THEN gross_amount ELSE 0 END),0) FROM cashbook WHERE school_id=? AND date BETWEEN ? AND ?", (school_id, _from, _to)).fetchone()
        total_income_f, total_expense_f = int(_cash[0]), int(_cash[1])
        cash_f = total_income_f - total_expense_f
        # Today = last day of timeline (To date) - so box follows timeline
        _today = conn2.execute("SELECT IFNULL(SUM(CASE WHEN type='income' THEN gross_amount ELSE 0 END),0), IFNULL(SUM(CASE WHEN type='expense' THEN gross_amount ELSE 0 END),0) FROM cashbook WHERE school_id=? AND date=?", (school_id, _to)).fetchone()
        today_income_f, today_expense_f = int(_today[0]), int(_today[1])
        # Expenses / Income filtered by timeline
        exp_total_f = conn2.execute("SELECT IFNULL(SUM(amount),0) FROM expenses WHERE school_id=? AND date BETWEEN ? AND ?", (school_id, _from, _to)).fetchone()[0]
        inc_total_f = conn2.execute("SELECT IFNULL(SUM(amount),0) FROM income WHERE school_id=? AND date BETWEEN ? AND ?", (school_id, _from, _to)).fetchone()[0]
        # Defaulter for month of To date
        try:
            _def_month = MONTHS[pd.to_datetime(_to).month-1]
        except Exception:
            _def_month = cur_month
        def_count_f = conn2.execute(f"SELECT COUNT(*) FROM students s LEFT JOIN fees f ON s.id=f.student_id AND f.month=? AND f.school_id=? WHERE s.school_id=? AND s.gender IN ({_g_ph}) AND s.class IN ({_c_ph}) AND (f.id IS NULL OR f.due_fee>0)", (_def_month, school_id, school_id)).fetchone()[0]
        def_due_f = conn2.execute(f"SELECT IFNULL(SUM(s.monthly_fee - IFNULL(f.paid_fee,0)),0) FROM students s LEFT JOIN fees f ON s.id=f.student_id AND f.month=? AND f.school_id=? WHERE s.school_id=? AND s.gender IN ({_g_ph}) AND s.class IN ({_c_ph}) AND (f.id IS NULL OR f.due_fee>0)", (_def_month, school_id, school_id)).fetchone()[0]
        conn2.close()
        # Override globals with filtered values for boxes in this section
        total_students, exp_fee, avg_fee, nclass, male, female = total_students_f, exp_fee_f, avg_fee_f, nclass_f, male_f, female_f
        total_paid, total_due, coll = total_paid_f, total_due_f, coll_f
        total_income, total_expense, cash_in_hand = total_income_f, total_expense_f, cash_f
        today_income, today_expense = today_income_f, today_expense_f
        exp_total, inc_total = int(exp_total_f), int(inc_total_f)
        def_count, def_due = int(def_count_f), int(def_due_f)
    except Exception as e:
        st.caption(f"Filter note: {e}")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("### 📊 At a Glance")
    if section=="dashboard":
        # ALL boxes in Dashboard
        show_boxes([
            ("Total Students", f"{total_students}", "#e3f2fd", "👨🎓"),
            ("Income (To Date)", f"Rs. {today_income:,}", "#e8f5e9", "💰"),
            ("Expense (To Date)", f"Rs. {today_expense:,}", "#ffebee", "💸"),
            ("Cash In Hand (Timeline)", f"Rs. {cash_in_hand:,}", "#fff3e0", "💵"),
            ("Total Income (Timeline)", f"Rs. {total_income:,}", "#e8f5e9", "📈"),
            ("Total Expense (Timeline)", f"Rs. {total_expense:,}", "#ffebee", "📉"),
            ("Total Fees Collected", f"Rs. {total_paid:,}", "#e3f2fd", "🧾"),
            ("Timeline To", f"{_to}", "#f3e5f5", "📅"),
        ])
    elif section=="students":
        show_boxes([
            ("Total Students", f"{total_students}", "#e3f2fd", "👨🎓"),
            ("Male Students", f"{male}", "#e3f2fd", "👦"),
            ("Female Students", f"{female}", "#fce4ec", "👧"),
            ("Classes", f"{nclass}", "#f3e5f5", "🏫"),
            ("Total Expected Fee", f"Rs. {int(exp_fee):,}", "#e8f5e9", "💰"),
            ("Average Fee", f"Rs. {int(avg_fee):,}", "#fff3e0", "📊"),
        ])
    elif section=="fees":
        show_boxes([
            ("Total Expected Fee", f"Rs. {int(exp_fee):,}", "#e3f2fd", "🧾"),
            ("Total Paid Fee", f"Rs. {int(total_paid):,}", "#e8f5e9", "✅"),
            ("Total Due Fee", f"Rs. {int(total_due):,}", "#ffebee", "⚠️"),
            ("Collection Rate", f"{coll}%", "#fff3e0", "📈"),
        ])
    elif section=="defaulter":
        show_boxes([
            ("Defaulters", f"{def_count}", "#ffebee", "🚨"),
            ("Defaulter Due", f"Rs. {int(def_due):,}", "#ffebee", "💸"),
            ("Total Students", f"{total_students}", "#e3f2fd", "👨🎓"),
            ("Collection Rate", f"{coll}%", "#e8f5e9", "📈"),
        ])
    elif section=="cashbook":
        show_boxes([
            ("Income (To Date)", f"Rs. {today_income:,}", "#e8f5e9", "💰"),
            ("Expense (To Date)", f"Rs. {today_expense:,}", "#ffebee", "💸"),
            ("Cash In Hand (Timeline)", f"Rs. {cash_in_hand:,}", "#fff3e0", "💵"),
            ("Total Income (Timeline)", f"Rs. {total_income:,}", "#e8f5e9", "📈"),
            ("Total Expense (Timeline)", f"Rs. {total_expense:,}", "#ffebee", "📉"),
        ])
    elif section=="expenses":
        show_boxes([
            ("Total Expenses", f"Rs. {int(exp_total):,}", "#ffebee", "💸"),
            ("Expense (To Date)", f"Rs. {int(today_expense):,}", "#ffebee", "📅"),
            ("Cash In Hand", f"Rs. {cash_in_hand:,}", "#fff3e0", "💵"),
            ("Top Category", f"{top_cat}", "#f3e5f5", "🏆"),
        ])
    elif section=="income":
        show_boxes([
            ("Total Other Income", f"Rs. {int(inc_total):,}", "#e8f5e9", "💵"),
            ("Income (To Date)", f"Rs. {int(today_income):,}", "#e8f5e9", "📅"),
            ("Total Fees Collected", f"Rs. {total_paid:,}", "#e3f2fd", "🧾"),
            ("Top Source", f"{top_src}", "#f3e5f5", "🏆"),
        ])
    else:
        # Change Password / Reports - show school summary boxes
        show_boxes([
            ("Total Students", f"{total_students}", "#e3f2fd", "👨🎓"),
            ("Cash In Hand", f"Rs. {cash_in_hand:,}", "#fff3e0", "💵"),
            ("Total Income", f"Rs. {total_income:,}", "#e8f5e9", "📈"),
            ("Total Expense", f"Rs. {total_expense:,}", "#ffebee", "📉"),
        ])
    st.divider()

if menu=="📊 Dashboard":
    st.title(f"Dashboard - {school_name}")
    show_top_totals("dashboard")
    # REMOVED duplicate metrics below - Top Boxes already show Total Students / Today Income / Expense / Cash / Total Income / Expense / Fees.
    # No second copy now, so Dashboard is clean: Boxes on Top -> Charts -> Recent Cashbook only.
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    conn=get_conn()
    df=pd.read_sql("SELECT date, type, gross_amount, description FROM cashbook WHERE school_id=? ORDER BY id DESC LIMIT 10", conn, params=(school_id,))
    class_df=pd.read_sql("SELECT class, COUNT(*) as students, SUM(monthly_fee) as total_fee FROM students WHERE school_id=? GROUP BY class", conn, params=(school_id,))
    month_df=pd.read_sql("SELECT month, SUM(paid_fee) as paid FROM fees WHERE school_id=? GROUP BY month", conn, params=(school_id,))
    cash_df=pd.read_sql("SELECT date, SUM(CASE WHEN type='income' THEN gross_amount ELSE 0 END) as income, SUM(CASE WHEN type='expense' THEN gross_amount ELSE 0 END) as expense FROM cashbook WHERE school_id=? GROUP BY date ORDER BY date", conn, params=(school_id,))
    conn.close()
    st.subheader("📊 Charts - Like Easy Charts App (Big, Clean)")
    if charts_on():
        st.markdown("### 🏫 Class-wise Students")
        if not class_df.empty: p_bar(class_df, "class", "students", "Students by Class")
        st.markdown("### 💰 Month-wise Fee Collected")
        if not month_df.empty: p_bar(month_df, "month", "paid", "Fees Collected by Month")
        st.markdown("### 📈 Income vs Expense by Date")
        if not cash_df.empty: p_line(cash_df, "date", ["income","expense"], "Income vs Expense")
        st.info("📖 Read like this: Tall bar = more students / more fee that month. Line up = profit, line down = loss.")
    else:
        st.caption("📊 Big charts hidden - press Show Charts in sidebar")
    st.subheader("📊 Charts - Press Show Charts in Sidebar")
    st.info("📖 Chart-wise Detail: 1) Students by Class = which class is biggest  2) Fees by Month = which month collected most  3) Income vs Expense = profit or loss by day")
    cc1,cc2=st.columns(2)
    with cc1:
        st.markdown("**Students by Class**")
        if charts_on() and (not class_df.empty): st.bar_chart(class_df.set_index("class")[["students"]])
        else: st.info("No students yet")
    with cc2:
        st.markdown("**Fees Collected by Month**")
        if charts_on() and (not month_df.empty): st.bar_chart(month_df.set_index("month")[["paid"]])
        else: st.info("No fees yet")
    st.markdown("**Income vs Expense by Date**")
    if charts_on() and (not cash_df.empty): st.line_chart(cash_df.set_index("date")[["income","expense"]])
    # LIGHT DASHBOARD - analysis is HIDDEN until you open it. This is the loading fix.
    with st.expander("📈 Detailed Data Analysis - Click to Open (All Sections)", expanded=False):
        _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
        for _line in insights_text(_a): st.info(_line)
        st.markdown("**Class-wise Students + Expected Fee**"); st.dataframe(_a['by_class'], width="stretch")
        st.markdown("**Month-wise Fees + Collection Rate %**"); st.dataframe(_a['fees_by_month'], width="stretch")
        st.markdown("**Expenses by Category**"); st.dataframe(_a['exp_by_cat'], width="stretch")
        st.markdown("**Income by Source**"); st.dataframe(_a['inc_by_src'], width="stretch")
    if st.button("📄 Prepare ALL Analysis PDF", key="prep_pdf_dash"):
        st.session_state["show_pdf_dash"]=True
    if st.session_state.get("show_pdf_dash"):
        with st.spinner("Making PDF... one time only"):
            _pdf=make_analysis_pdf(school_name, school_id)
        if _pdf: st.download_button("⬇️ Download ALL Analysis PDF", _pdf, f"{school_name}_ALL_ANALYSIS.pdf", mime="application/pdf", width="stretch", key="pdf_dash")
    if total_students==0:
        st.warning(f"⚠️ Showing 0 students - this means a NEW empty database was created here: {DB_PATH}. Your old data is in a different folder's schools.db. Copy your old schools.db into this same folder as school.py / app.py, then click Refresh Data.")
    st.subheader("Recent Cashbook"); st.dataframe(df, width="stretch")

elif menu=="👨🎓 Students":
    st.title("Students - CRUD")
    show_top_totals("students")
    # EDIT MODE
    edit_id=st.session_state.get("editing_students")
    if edit_id:
        conn=get_conn(); r=conn.execute("SELECT * FROM students WHERE id=? AND school_id=?", (edit_id,school_id)).fetchone(); conn.close()
        if r:
            st.markdown(f"### ✏️ Editing: {r['name']} (GR {r['gr']})")
            with st.form("edit_student"):
                c1,c2,c3=st.columns(3)
                with c1: gr=st.text_input("GR No", value=r["gr"]); name=st.text_input("Name", value=r["name"])
                with c2: father=st.text_input("Father", value=r["father"]); surname=st.text_input("Surname", value=str(r["surname"] or ""))
                with c3: cls=st.selectbox("Class", CLASSES, index=CLASSES.index(r["class"]) if r["class"] in CLASSES else 0); fee=st.number_input("Monthly Fee", value=int(r["monthly_fee"] or 0)); gender=st.selectbox("Gender", ["Male","Female"], index=0 if (r["gender"] if "gender" in r.keys() else "Male")!="Female" else 1)
                cc1,cc2=st.columns(2)
                with cc1:
                    if st.form_submit_button("💾 Save Changes"):
                        conn=get_conn(); conn.execute("UPDATE students SET gr=?, name=?, father=?, surname=?, class=?, monthly_fee=?, gender=? WHERE id=?", (gr,name,father,surname,cls,fee,gender,edit_id)); conn.commit(); conn.close(); st.session_state["editing_students"]=None; st.success("Updated!"); st.rerun()
                with cc2:
                    if st.form_submit_button("Cancel"):
                        st.session_state["editing_students"]=None; st.rerun()
    else:
        with st.form("add_student", clear_on_submit=True):
            c1,c2,c3=st.columns(3)
            with c1: gr=st.text_input("GR No *"); name=st.text_input("Name *")
            with c2: father=st.text_input("Father Name *"); surname=st.text_input("Surname")
            with c3: cls=st.selectbox("Class", CLASSES); fee=st.number_input("Monthly Fee", min_value=0, value=2000); gender=st.selectbox("Gender", ["Male","Female"])
            if st.form_submit_button("Add Student"):
                if gr and name:
                    conn=get_conn(); conn.execute("INSERT INTO students (school_id, gr, name, father, surname, class, monthly_fee, gender) VALUES (?,?,?,?,?,?,?,?)",(school_id,gr,name,father,surname,cls,fee,gender)); conn.commit(); conn.close(); st.success(f"Student Added! Gender: {gender}"); st.rerun()
                else: st.error("GR and Name required")
    conn=get_conn(); df=pd.read_sql("SELECT * FROM students WHERE school_id=? ORDER BY class, gr", conn, params=(school_id,)); conn.close()
    st.caption(f"Total: {len(df)} students")
    if not df.empty:
        _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
        st.subheader("📈 Detailed Students Analysis")
        # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
        st.markdown("**Class-wise: Students / Total Fee / Avg Fee**"); st.dataframe(_a['by_class'], width="stretch")
        st.markdown("### 📊 Big Charts - Like Easy Charts App")
        if charts_on():
            st.markdown("#### 👦👧 Male vs Female")
            if not _a['by_gender'].empty: p_pie(_a['by_gender']["gender"].tolist(), _a['by_gender']["count"].tolist(), "Male vs Female Students", colors=["#1f77b4","#e377c2"])
            st.markdown("#### 🏫 Students by Class")
            if not _a['by_class'].empty: p_bar(_a['by_class'], "class", "total_students", "Students by Class")
            st.markdown("#### 💰 Expected Fee by Class")
            if not _a['by_class'].empty: p_bar(_a['by_class'], "class", "total_expected_fee", "Expected Fee by Class", color="#2ca02c")
        else:
            st.caption("📊 Big charts hidden - press Show Charts")
        st.markdown("**👦👧 Gender-wise: Male / Female**")
        st.info("📖 Gender Chart Detail: Blue bar Male, next bar Female. If Female bar is very small, need more girls admission in that class.")
        # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
        st.dataframe(_a['by_gender'], width="stretch")
        if charts_on() and (not _a['by_gender'].empty): st.bar_chart(_a['by_gender'].set_index("gender")[["count"]])
        st.markdown("**Gender by Class**")
        if "gender" in df.columns: st.dataframe(df.groupby(["class","gender"]).size().reset_index(name="count"), width="stretch")
        st.markdown("**Surname-wise Count**"); st.dataframe(_a['by_surname'], width="stretch")
        if charts_on():
            st.bar_chart(df.groupby("class").size())  # only when Show Charts pressed
        else:
            st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
        if charts_on():
            st.bar_chart(_a['by_class'].set_index("class")[["total_expected_fee"]])  # only when Show Charts pressed
        else:
            st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
        st.info(f"Insight: Class with most students is {_a['by_class'].sort_values('total_students',ascending=False).iloc[0]['class'] if not _a['by_class'].empty else '-'}. Class with highest fee collection potential is {_a['by_class'].sort_values('total_expected_fee',ascending=False).iloc[0]['class'] if not _a['by_class'].empty else '-'}.")
        if st.button("📄 Prepare PDF", key="prep_pdf_stu"):
            st.session_state["show_pdf_stu"]=True
        if st.session_state.get("show_pdf_stu"):
            _pdf=make_analysis_pdf(school_name, school_id)
            if _pdf: st.download_button("📄 Download ALL Analysis PDF", _pdf, f"{school_name}_ALL_ANALYSIS.pdf", mime="application/pdf", key="pdf_stu")
        crud_table(df, "students")
    st.download_button("Download Students CSV", df.to_csv(index=False), "students.csv")

elif menu=="💰 Collect Fee":
    st.title("Collect Fee - CRUD")
    show_top_totals("fees")
    conn=get_conn(); students=pd.read_sql("SELECT * FROM students WHERE school_id=? ORDER BY gr", conn, params=(school_id,)); conn.close()
    if students.empty: st.warning("No students yet.")
    else:
        # STEP 1 - FIRST select Class
        st.markdown("### Step 1 - Select Class First")
        fee_class = st.selectbox("Select Class", ["All Classes"] + CLASSES, key="fee_class_first")
        if fee_class != "All Classes":
            students = students[students["class"]==fee_class]
        st.info(f"Showing {len(students)} students in Class: {fee_class}")
        if students.empty:
            st.warning(f"No students in {fee_class}. Select another class.")
            st.stop()
        # STEP 2 - THEN select Student from that class only
        st.markdown("### Step 2 - Select Student (from selected Class only)")
        students["label"]=students["gr"].astype(str)+" - "+students["name"]+" ("+students["class"]+") - "+students["gender"].astype(str) if "gender" in students.columns else students["gr"].astype(str)+" - "+students["name"]+" ("+students["class"]+")"
        sel=st.selectbox("Select Student", students["label"].tolist(), key="fee_student_list"); row=students[students["label"]==sel].iloc[0]
        st.info(f"**{row['name']}** | Father: {row['father']} | Class: {row['class']} | Monthly Fee: Rs. {row['monthly_fee']}")
        with st.form("fee_form"):
            c1,c2,c3=st.columns(3)
            with c1: month=st.selectbox("Select Month", MONTHS, index=10)
            with c2: paid=st.number_input("Paid Fee", min_value=0, value=int(row["monthly_fee"]))
            with c3: monthly_fee=st.number_input("Monthly Fee", min_value=0, value=int(row["monthly_fee"]))
            due=monthly_fee-paid; st.write(f"**Due: Rs. {due}** | Date: {date.today()}")
            if st.form_submit_button("Save Fee + Add to Cashbook"):
                conn=get_conn(); already=conn.execute("SELECT * FROM fees WHERE school_id=? AND student_id=? AND month=?", (school_id,int(row["id"]),month)).fetchone()
                if already: st.error(f"Already paid for {month}! Paid: {already['paid_fee']}, Due: {already['due_fee']}")
                else:
                    conn.execute("INSERT INTO fees (school_id, student_id, month, monthly_fee, paid_fee, due_fee, submit_date) VALUES (?,?,?,?,?,?,?)",(school_id,int(row["id"]),month,monthly_fee,paid,due,date.today().isoformat()))
                    conn.execute("INSERT INTO cashbook (school_id, date, type, gross_amount, description) VALUES (?,?, 'income', ?, ?)",(school_id,date.today().isoformat(),paid,f"Fee {month} - {row['name']} GR {row['gr']}"))
                    conn.commit(); st.success(f"Saved! Due: Rs. {due}")
                conn.close()
        # CRUD for this student's fees
        st.subheader("Fee History - Edit / Delete")
        conn=get_conn(); fdf=pd.read_sql("SELECT * FROM fees WHERE school_id=? AND student_id=? ORDER BY id DESC", conn, params=(school_id,int(row["id"]))); conn.close()
        if not fdf.empty:
            st.dataframe(fdf, width="stretch")
            flabels=[f"ID {r.id} | {r.month} | Paid {r.paid_fee} | Due {r.due_fee}" for r in fdf.itertuples()]
            fsel=st.selectbox("Select Fee Record", flabels, key="fee_sel")
            fid=int(fsel.split("|")[0].replace("ID","").strip())
            frow=fdf[fdf["id"]==fid].iloc[0]
            with st.form("edit_fee"):
                fc1,fc2,fc3=st.columns(3)
                with fc1: fmonth=st.selectbox("Month", MONTHS, index=MONTHS.index(frow["month"]) if frow["month"] in MONTHS else 0)
                with fc2: fpaid=st.number_input("Paid Fee", value=int(frow["paid_fee"] or 0))
                with fc3: fmf=st.number_input("Monthly Fee", value=int(frow["monthly_fee"] or 0))
                if st.form_submit_button("💾 Update Fee"):
                    conn=get_conn(); conn.execute("UPDATE fees SET month=?, monthly_fee=?, paid_fee=?, due_fee=? WHERE id=?", (fmonth,fmf,fpaid,fmf-fpaid,fid)); conn.commit(); conn.close(); st.success("Fee Updated!"); st.rerun()
            if st.button("🗑️ Delete This Fee Record"):
                conn=get_conn(); conn.execute("DELETE FROM fees WHERE id=?", (fid,)); conn.commit(); conn.close(); st.success("Fee Deleted - Note: Cashbook entry stays, delete it from Cashbook if needed"); st.rerun()
        # Detailed Fees Analysis for this student + all school
        _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
        st.subheader("📈 Detailed Fees Analysis (Whole School)")
        # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
        st.markdown("### 📊 Big Charts - Fees Like Easy Charts App")
        if charts_on():
            st.markdown("#### 💰 Paid vs Due by Month")
            if not _a['fees_by_month'].empty: p_bar(_a['fees_by_month'], "month", "paid", "Paid Fee by Month", color="#2ca02c")
            st.markdown("#### 📊 Collection Rate % by Month")
            if not _a['fees_by_month'].empty: p_bar(_a['fees_by_month'], "month", "collection_rate_%", "Collection Rate % by Month", color="#ff7f0e")
            st.markdown("#### 🥧 Paid vs Due (Total)")
            p_pie(["Paid","Due"], [float(_a['total_paid']), float(_a['total_due'])], "Paid vs Due - Total", colors=["#2ca02c","#d62728"])
        else:
            st.caption("📊 Big charts hidden - press Show Charts")
        st.markdown("**Month-wise Fees + Collection Rate**"); st.dataframe(_a['fees_by_month'], width="stretch")
        if not _a['fees_by_month'].empty:
            if charts_on():
                st.bar_chart(_a['fees_by_month'].set_index("month")[["paid","due"]])  # only when Show Charts pressed
            else:
                st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
            if charts_on():
                st.bar_chart(_a['fees_by_month'].set_index("month")[["collection_rate_%"]])  # only when Show Charts pressed
            else:
                st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
            st.info(f"Insight: Best month {_a['fees_by_month'].sort_values('paid',ascending=False).iloc[0]['month']} collected Rs.{int(_a['fees_by_month'].sort_values('paid',ascending=False).iloc[0]['paid'])}. Lowest month {_a['fees_by_month'].sort_values('paid').iloc[0]['month']} needs follow-up.")
        if st.button("📄 Prepare PDF", key="prep_pdf_fee"):
            st.session_state["show_pdf_fee"]=True
        if st.session_state.get("show_pdf_fee"):
            _pdf=make_analysis_pdf(school_name, school_id)
            if _pdf: st.download_button("📄 Download ALL Analysis PDF", _pdf, f"{school_name}_ALL_ANALYSIS.pdf", mime="application/pdf", key="pdf_fee")
        if charts_on() and (not fdf.empty): st.bar_chart(fdf.set_index("month")[["paid_fee"]])

elif menu=="🚨 Defaulter List":
    st.title("Defaulter List - Classwise & Monthwise")
    show_top_totals("defaulter")
    c1,c2=st.columns(2)
    with c1: fclass=st.selectbox("Select Class", ["All"]+CLASSES)
    with c2: fmonth=st.selectbox("Select Month", MONTHS, index=10)
    query="""SELECT s.gr, s.name, s.father, s.surname, s.class, s.gender, s.monthly_fee, IFNULL(f.paid_fee,0) as paid_fee, s.monthly_fee - IFNULL(f.paid_fee,0) as due_fee, CASE WHEN f.paid_fee IS NULL THEN 'Not Paid' ELSE 'Partial Paid' END as status FROM students s LEFT JOIN fees f ON s.id=f.student_id AND f.month=? AND f.school_id=? WHERE s.school_id=? AND (f.id IS NULL OR f.due_fee>0)"""
    params=[fmonth, school_id, school_id]
    if fclass!="All": query+=" AND s.class=?"; params.append(fclass)
    query+=" ORDER BY s.class, s.gr"
    conn=get_conn(); df=pd.read_sql(query, conn, params=params); conn.close()
    st.markdown("### 📊 Big Charts - Defaulter Like Easy Charts App")
    if charts_on():
        if not df.empty:
            _dc = df.groupby("class")["due_fee"].sum().reset_index()
            p_bar(_dc, "class", "due_fee", "Defaulter Due by Class", color="#d62728")
            _ds = df.groupby("status")["due_fee"].sum().reset_index()
            p_pie(_ds["status"].tolist(), _ds["due_fee"].tolist(), "Not Paid vs Partial Paid", colors=["#d62728","#ff7f0e"])
        else:
            st.info("No defaulters - all paid! 🎉")
    else:
        st.caption("📊 Big charts hidden - press Show Charts")
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    st.dataframe(df, width="stretch")
    if not df.empty:
        _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
        st.subheader("📈 Detailed Defaulter Analysis")
        st.markdown("**Defaulter by Class**"); st.dataframe(df.groupby("class").agg(defaulters=("gr","count"), total_due=("due_fee","sum"), avg_due=("due_fee","mean")).reset_index(), width="stretch")
        st.markdown("**Defaulter by Status**"); st.dataframe(df.groupby("status").agg(count=("gr","count"), total_due=("due_fee","sum")).reset_index(), width="stretch")
        if charts_on():
            st.bar_chart(df.groupby("class")["due_fee"].sum())  # only when Show Charts pressed
        else:
            st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
        st.info(f"Insight: Total {len(df)} defaulters owe Rs.{int(df['due_fee'].sum())}. Class with highest due: {df.groupby('class')['due_fee'].sum().idxmax()}. {df[df['status']=='Not Paid'].shape[0]} students paid NOTHING, {df[df['status']=='Partial Paid'].shape[0]} paid PARTIAL. Call Not Paid first.")
        if st.button("📄 Prepare PDF", key="prep_pdf_def"):
            st.session_state["show_pdf_def"]=True
        if st.session_state.get("show_pdf_def"):
            _pdf=make_analysis_pdf(school_name, school_id)
            if _pdf: st.download_button("📄 Download ALL Analysis PDF", _pdf, f"{school_name}_ALL_ANALYSIS.pdf", mime="application/pdf", key="pdf_def")
        if charts_on():
            st.bar_chart(df.set_index("name")[["due_fee"]])  # only when Show Charts pressed
        else:
            st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
        st.download_button("Download Defaulter CSV", df.to_csv(index=False), f"defaulter_{fclass}_{fmonth}.csv")
        pdf=make_pdf(school_name, school_id, fmonth)
        if pdf: st.download_button("📄 Download Defaulter / Report PDF", pdf, f"report_{school_name}_{fmonth}.pdf", mime="application/pdf")

elif menu=="📒 Cashbook":
    st.title("Cashbook - CRUD")
    show_top_totals("cashbook")
    sel_date=st.date_input("Select Date", value=date.today())
    conn=get_conn(); df=pd.read_sql("SELECT * FROM cashbook WHERE school_id=? AND date=? ORDER BY id", conn, params=(school_id, sel_date.isoformat())); all_df=pd.read_sql("SELECT * FROM cashbook WHERE school_id=? ORDER BY id DESC LIMIT 100", conn, params=(school_id,)); conn.close()
    c1,c2,c3=st.columns(3)
    inc=df[df["type"]=="income"]["gross_amount"].sum() if not df.empty else 0; exp=df[df["type"]=="expense"]["gross_amount"].sum() if not df.empty else 0
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    st.subheader(f"Cashbook for {sel_date} - Edit / Delete")
    if not df.empty:
        st.dataframe(df, width="stretch")
        labels=[f"ID {r.id} | {r.type} | Rs.{r.gross_amount} | {r.description}" for r in df.itertuples()]
        csel=st.selectbox("Select Cashbook Entry", labels, key="cash_sel"); cid=int(csel.split("|")[0].replace("ID","").strip()); crow=df[df["id"]==cid].iloc[0]
        with st.form("edit_cash"):
            cc1,cc2=st.columns(2)
            with cc1: camt=st.number_input("Amount", value=int(crow["gross_amount"] or 0)); ctype=st.selectbox("Type", ["income","expense"], index=0 if crow["type"]=="income" else 1)
            with cc2: cdesc=st.text_input("Description", value=str(crow["description"] or "")); cdate=st.date_input("Date", value=date.fromisoformat(crow["date"]))
            if st.form_submit_button("💾 Update Cashbook"):
                conn=get_conn(); conn.execute("UPDATE cashbook SET gross_amount=?, type=?, description=?, date=? WHERE id=?", (camt,ctype,cdesc,cdate.isoformat(),cid)); conn.commit(); conn.close(); st.success("Updated!"); st.rerun()
        if st.button("🗑️ Delete Cashbook Entry"):
            conn=get_conn(); conn.execute("DELETE FROM cashbook WHERE id=?", (cid,)); conn.commit(); conn.close(); st.success("Deleted!"); st.rerun()
    st.subheader("All Cashbook (Last 100)"); st.dataframe(all_df, width="stretch")
    _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
    st.subheader("📈 Detailed Cashbook Analysis")
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    st.markdown("**Cashbook by Date (Income vs Expense)**"); st.dataframe(_a['cash_by_date'], width="stretch")
    st.info(f"Insight: Income Rs.{_a['total_income_cash']} vs Expense Rs.{_a['total_exp_cash']}. Net Rs.{_a['cash_in_hand']}. Best income day {_a['best_income_day']}, highest expense day {_a['best_expense_day']}.")
    if st.button("📄 Prepare PDF", key="prep_pdf_cash"):
        st.session_state["show_pdf_cash"]=True
    if st.session_state.get("show_pdf_cash"):
        _pdf=make_analysis_pdf(school_name, school_id)
        if _pdf: st.download_button("📄 Download ALL Analysis PDF", _pdf, f"{school_name}_ALL_ANALYSIS.pdf", mime="application/pdf", key="pdf_cash")
    if not all_df.empty:
        chart_df=all_df.copy(); chart_df["date"]=pd.to_datetime(chart_df["date"])
        if charts_on(): st.line_chart(chart_df.groupby(["date","type"])["gross_amount"].sum().unstack(fill_value=0))
    st.info(f"Cash In Hand: Rs. {cash_in_hand}")

elif menu=="💸 Expenses":
    st.title("Expenses - CRUD")
    show_top_totals("expenses")
    with st.form("exp_form", clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1: cat=st.selectbox("Category", ["Salary","Electricity","Repair","Books","Stationery","Transport","Rent","Other"])
        with c2: amt=st.number_input("Amount", min_value=0)
        desc=st.text_input("Description"); exp_date=st.date_input("Date", value=date.today())
        if st.form_submit_button("Save Expense"):
            conn=get_conn(); conn.execute("INSERT INTO expenses (school_id, date, category, amount, description) VALUES (?,?,?,?,?)",(school_id,exp_date.isoformat(),cat,amt,desc)); conn.execute("INSERT INTO cashbook (school_id, date, type, gross_amount, description) VALUES (?,?, 'expense', ?, ?)",(school_id,exp_date.isoformat(),amt,f"Expense - {cat} - {desc}")); conn.commit(); conn.close(); st.success("Saved + Cashbook"); st.rerun()
    conn=get_conn(); df=pd.read_sql("SELECT * FROM expenses WHERE school_id=? ORDER BY id DESC LIMIT 50", conn, params=(school_id,)); conn.close()
    if not df.empty:
        st.dataframe(df.drop(columns=["id"], errors="ignore"), width="stretch")
    else:
        st.info("No expenses")
    if not df.empty:
        _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
        st.subheader("📈 Detailed Expenses Analysis")
        # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
        st.markdown("### 📊 Big Charts - Expenses")
        if charts_on():
            if not _a['exp_by_cat'].empty:
                p_bar(_a['exp_by_cat'], "category", "total", "Expenses by Category", color="#d62728")
                p_pie(_a['exp_by_cat']["category"].tolist(), _a['exp_by_cat']["total"].tolist(), "Expenses Share by Category")
        else:
            st.caption("📊 Big charts hidden - press Show Charts")
        st.dataframe(_a['exp_by_cat'], width="stretch")
        st.markdown("**Expenses by Date**"); st.dataframe(_a['exp_by_date'], width="stretch")
        if charts_on():
            st.bar_chart(df.groupby("category")["amount"].sum())  # only when Show Charts pressed
        else:
            st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
        st.info(f"Insight: Biggest expense is {_a['top_expense_cat']} Rs.{_a['top_expense_amt']} = {round(_a['top_expense_amt']/int(df['amount'].sum())*100,1) if int(df['amount'].sum()) else 0}% of all expenses. Cut this first.")
        if st.button("📄 Prepare PDF", key="prep_pdf_exp"):
            st.session_state["show_pdf_exp"]=True
        if st.session_state.get("show_pdf_exp"):
            _pdf=make_analysis_pdf(school_name, school_id)
            if _pdf: st.download_button("📄 Download ALL Analysis PDF", _pdf, f"{school_name}_ALL_ANALYSIS.pdf", mime="application/pdf", key="pdf_exp")
        crud_table(df, "expenses")

elif menu=="💵 Income":
    st.title("Other Income - CRUD")
    show_top_totals("income")
    st.caption("Fees go automatically from Collect Fee. Use this only for: Admission Fee | Exam Fee | Income | Other")
    with st.form("inc_form", clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1: src=st.selectbox("Source", ["Admission Fee","Exam Fee","Income","Other"])
        with c2: amt=st.number_input("Amount", min_value=0)
        desc=st.text_input("Description"); inc_date=st.date_input("Date", value=date.today())
        if st.form_submit_button("Save Income"):
            conn=get_conn(); conn.execute("INSERT INTO income (school_id, date, source, amount, description) VALUES (?,?,?,?,?)",(school_id,inc_date.isoformat(),src,amt,desc)); conn.execute("INSERT INTO cashbook (school_id, date, type, gross_amount, description) VALUES (?,?, 'income', ?, ?)",(school_id,inc_date.isoformat(),amt,f"Income - {src} - {desc}")); conn.commit(); conn.close(); st.success("Saved + Cashbook"); st.rerun()
    conn=get_conn(); df=pd.read_sql("SELECT * FROM income WHERE school_id=? ORDER BY id DESC LIMIT 50", conn, params=(school_id,)); conn.close()
    if not df.empty:
        st.dataframe(df.drop(columns=["id"], errors="ignore"), width="stretch")
    else:
        st.info("No income")
    if not df.empty:
        _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
        st.subheader("📈 Detailed Other Income Analysis")
        # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
        st.markdown("### 📊 Big Charts - Income (Admission / Exam / Income / Other)")
        if charts_on():
            if not _a['inc_by_src'].empty:
                p_bar(_a['inc_by_src'], "source", "total", "Income by Source", color="#2ca02c")
                p_pie(_a['inc_by_src']["source"].tolist(), _a['inc_by_src']["total"].tolist(), "Income Share - Admission / Exam / Income / Other", colors=["#1f77b4","#2ca02c","#ff7f0e","#9467bd"])
        else:
            st.caption("📊 Big charts hidden - press Show Charts")
        st.dataframe(_a['inc_by_src'], width="stretch")
        if charts_on():
            st.bar_chart(df.groupby("source")["amount"].sum())  # only when Show Charts pressed
        else:
            st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
        st.info(f"Insight: Top other income source is {_a['top_income_src']}. Fees are still main income - other income is only Rs.{int(df['amount'].sum())} vs fees Rs.{_a['total_paid']}.")
        if st.button("📄 Prepare PDF", key="prep_pdf_inc"):
            st.session_state["show_pdf_inc"]=True
        if st.session_state.get("show_pdf_inc"):
            _pdf=make_analysis_pdf(school_name, school_id)
            if _pdf: st.download_button("📄 Download ALL Analysis PDF", _pdf, f"{school_name}_ALL_ANALYSIS.pdf", mime="application/pdf", key="pdf_inc")
        crud_table(df, "income")

elif menu=="👥 Users":
    st.title("Users - CRUD + Change Password")
    edit_u=st.session_state.get("editing_users")
    if edit_u:
        conn=get_conn(); r=conn.execute("SELECT * FROM users WHERE id=?", (edit_u,)).fetchone(); conn.close()
        if r:
            st.markdown(f"### ✏️ Editing User: {r['name']}")
            with st.form("edit_user"):
                un=st.text_input("Name", value=r["name"]); ro=st.selectbox("Role", ["school_admin","teacher","accountant"], index=["school_admin","teacher","accountant"].index(r["role"]) if r["role"] in ["school_admin","teacher","accountant"] else 0); us=st.text_input("Username", value=r["username"])
                if st.form_submit_button("💾 Save User"):
                    conn=get_conn(); conn.execute("UPDATE users SET name=?, role=?, username=? WHERE id=?", (un,ro,us,edit_u)); conn.commit(); conn.close(); st.session_state["editing_users"]=None; st.success("User Updated!"); st.rerun()
                if st.form_submit_button("Cancel"):
                    st.session_state["editing_users"]=None; st.rerun()
    else:
        with st.form("user_form", clear_on_submit=True):
            c1,c2,c3=st.columns(3)
            with c1: uname=st.text_input("Name")
            with c2: role=st.selectbox("Role", ["school_admin","teacher","accountant"])
            with c3: username=st.text_input("Username")
            pwd=st.text_input("Password", type="password")
            if st.form_submit_button("Add User"):
                conn=get_conn(); conn.execute("INSERT INTO users (school_id, name, role, username, password) VALUES (?,?,?,?,?)",(school_id,uname,role,username,pwd)); conn.commit(); conn.close(); st.success("User Added"); st.rerun()
    conn=get_conn(); df=pd.read_sql("SELECT * FROM users WHERE school_id=?", conn, params=(school_id,)); conn.close()
    if not df.empty:
        st.dataframe(df.drop(columns=["id","password"], errors="ignore"), width="stretch")
    else:
        st.info("No users")
    if not df.empty:
        _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
        st.subheader("📈 Detailed Users Analysis")
        st.dataframe(_a['users_by_role'], width="stretch")
        if charts_on():
            st.bar_chart(_a['users_by_role'].set_index("role")[["count"]])  # only when Show Charts pressed
        else:
            st.caption('📊 Chart hidden - press Show Charts button in sidebar to see this chart + detail')
        _roles = ", ".join([str(r.role)+"="+str(r.count) for r in _a['users_by_role'].itertuples()]) if not _a['users_by_role'].empty else "-"
        st.info(f"Insight: Total {len(df)} staff users. Roles: {_roles}")
        if st.button("📄 Prepare PDF", key="prep_pdf_users"):
            st.session_state["show_pdf_users"]=True
        if st.session_state.get("show_pdf_users"):
            _pdf=make_analysis_pdf(school_name, school_id)
            if _pdf: st.download_button("📄 Download ALL Analysis PDF", _pdf, f"{school_name}_ALL_ANALYSIS.pdf", mime="application/pdf", key="pdf_users")
        crud_table(df, "users")
        st.markdown("#### 🔑 Change Staff User Password")
        ulabels=[f"ID {r.id} | {r.name} ({r.username})" for r in df.itertuples()]
        usel=st.selectbox("Select User to Change Password", ulabels, key="user_pass_sel")
        uid=int(usel.split("|")[0].replace("ID","").strip())
        with st.form("change_user_pass"):
            np=st.text_input("New Password", type="password")
            if st.form_submit_button("🔑 Change Password"):
                if np:
                    conn=get_conn(); conn.execute("UPDATE users SET password=? WHERE id=?", (np.strip(),uid)); conn.commit(); conn.close(); st.success("Staff Password Changed!"); st.rerun()
                else: st.error("Enter new password")

elif menu=="🔑 Change Password":
    st.title("🔑 Change Password")
    show_top_totals("summary")
    st.markdown("### School Login Password (Your own school code password)")
    with st.form("change_school_own"):
        oldp=st.text_input("Current Password", type="password")
        newp=st.text_input("New Password", type="password")
        conf=st.text_input("Confirm New Password", type="password")
        if st.form_submit_button("Change My School Password"):
            conn=get_conn(); row=conn.execute("SELECT password FROM schools WHERE id=?", (school_id,)).fetchone()
            if not row or row["password"]!=oldp.strip(): st.error("Current password wrong!")
            elif newp.strip()!=conf.strip(): st.error("New passwords do not match!")
            elif len(newp.strip())<4: st.error("Password must be at least 4 characters")
            else:
                conn.execute("UPDATE schools SET password=? WHERE id=?", (newp.strip(),school_id)); conn.commit(); st.success(f"Password Changed! Next login use: {st.session_state.school_name} code + new password: {newp}")
            conn.close()
    st.markdown("---")
    st.info("✅ In School login there is NO Users / Add User. Only Change Password for your own school login is here. Super Admin controls users.")
elif menu=="📄 Reports / PDF":
    st.title("📊 Complete Data Analysis - All Sections + Download PDF")
    show_top_totals("dashboard")
    _a=get_analysis_cached(school_id, _db_mtime=float(DB_PATH.stat().st_mtime) if DB_PATH.exists() else 0)
    st.subheader("🔑 Executive Summary - Auto Insights")
    for _line in insights_text(_a): st.success(_line)
    st.divider()
    # One BIG download for ALL analysis
    _pdf_all=make_analysis_pdf(school_name, school_id)
    if _pdf_all:
        st.download_button("📄 ⬇️ DOWNLOAD ALL ANALYSIS PDF - Every Section in One File", _pdf_all, f"{school_name}_COMPLETE_ANALYSIS.pdf", mime="application/pdf", width="stretch", type="primary")
    else:
        st.error("Add reportlab to requirements.txt")
    st.divider()
    st.subheader("1️⃣ Students Analysis - Detailed")
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    st.markdown("**Gender-wise**"); st.dataframe(_a['by_gender'], width="stretch")
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    if charts_on() and not _a['by_gender'].empty: st.bar_chart(_a['by_gender'].set_index("gender")[["count"]])
    st.dataframe(_a['by_class'], width="stretch"); st.dataframe(_a['by_surname'], width="stretch")
    if charts_on() and (not _a['by_class'].empty): st.bar_chart(_a['by_class'].set_index("class")[["total_students","total_expected_fee"]])
    st.subheader("2️⃣ Fees Analysis - Detailed")
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    st.dataframe(_a['fees_by_month'], width="stretch")
    if charts_on() and (not _a['fees_by_month'].empty): st.bar_chart(_a['fees_by_month'].set_index("month")[["paid","due"]]); st.bar_chart(_a['fees_by_month'].set_index("month")[["collection_rate_%"]])
    st.subheader("3️⃣ Defaulter Analysis - Detailed")
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    st.subheader("4️⃣ Cashbook Analysis - Detailed")
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    st.dataframe(_a['cash_by_date'], width="stretch")
    if charts_on() and (not _a['cash_by_date'].empty and "income" in _a['cash_by_date'].columns): st.line_chart(_a['cash_by_date'].set_index("date")[["income","expense"]] if "expense" in _a['cash_by_date'].columns else _a['cash_by_date'].set_index("date")[["income"]])
    st.subheader("5️⃣ Expenses Analysis - Detailed")
    # REMOVED duplicate below - already shown in At a Glance boxes on top, so it will NOT appear again down
    st.dataframe(_a['exp_by_cat'], width="stretch"); st.dataframe(_a['exp_by_date'], width="stretch")
    if charts_on() and not _a['exp_by_cat'].empty: st.bar_chart(_a['exp_by_cat'].set_index("category")[["total"]])
    st.subheader("6️⃣ Other Income Analysis - Detailed")
    st.dataframe(_a['inc_by_src'], width="stretch")
    if charts_on() and (not _a['inc_by_src'].empty): st.bar_chart(_a['inc_by_src'].set_index("source")[["total"]])
    st.subheader("7️⃣ Users Analysis - Detailed")
    st.dataframe(_a['users_by_role'], width="stretch")
    st.divider()
    if _pdf_all: st.download_button("📄 ⬇️ DOWNLOAD ALL ANALYSIS PDF AGAIN", _pdf_all, f"{school_name}_COMPLETE_ANALYSIS.pdf", mime="application/pdf", width="stretch", key="pdf_all_bottom")
    st.subheader("⬇️ Also Download CSVs")
    c1,c2,c3=st.columns(3)
    with c1: st.download_button("Students CSV", _a['students'].to_csv(index=False), "students.csv")
    with c2: st.download_button("Fees CSV", _a['fees'].to_csv(index=False), "fees.csv")
    with c3: st.download_button("Cashbook CSV", _a['cash'].to_csv(index=False), "cashbook.csv")
