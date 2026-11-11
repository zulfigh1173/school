
import streamlit as st
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
import io

# PDF - using reportlab
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_PDF = True
except:
    HAS_PDF = False

st.set_page_config(page_title="School Management - ERP Management System", layout="wide", page_icon="🏫")
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
    c = conn.execute("SELECT COUNT(*) FROM schools").fetchone()[0]
    if c == 0:
        exp = (date.today()+timedelta(days=30)).isoformat()
        conn.execute("INSERT INTO schools (school_name, login_code, password, city, phone, plan, monthly_charge, expiry_date, payment_status) VALUES (?,?,?,?,?,?,?,?,?)", ("Govt School Ratodero","RATO01","1234","Ratodero","03001234567","Standard",2500,exp,"Paid"))
        conn.execute("INSERT INTO schools (school_name, login_code, password, city, phone, plan, monthly_charge, expiry_date, payment_status) VALUES (?,?,?,?,?,?,?,?,?)", ("City School Larkana","LARK02","5678","Larkana","03007654321","Basic",1500,exp,"Paid"))
        conn.commit()
        for gr,name,father,surname,cls,fee in [("101","Ali","Ahmed","Ghanghro","5th",2000),("102","Sara","Khan","Soomro","5th",2000),("103","Ahmed","Ali","Junejo","6th",2500),("104","Ayesha","Mohammed","Memon","6th",2500)]:
            conn.execute("INSERT INTO students (school_id, gr, name, father, surname, class, monthly_fee) VALUES (?,?,?,?,?,?,?)",(1,gr,name,father,surname,cls,fee))
        conn.commit()
    conn.close()
init_db()

MONTHS = ["Jan 2026","Feb 2026","Mar 2026","Apr 2026","May 2026","Jun 2026","Jul 2026","Aug 2026","Sep 2026","Oct 2026","Nov 2026","Dec 2026","Jan 2027","Feb 2027","Mar 2027"]
CLASSES = ["1st","2nd","3rd","4th","5th","6th","7th","8th","9th","10th"]

def make_pdf(title, headers, rows):
    """Generate PDF bytes from headers+rows"""
    if not HAS_PDF:
        return None
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>{title}</b>", styles['Title']), Spacer(1,12)]
    data = [headers] + [[str(c) for c in r] for r in rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#1F4E79")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),8),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor("#D9EAF3")]),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    elements.append(t)
    elements.append(Spacer(1,12))
    elements.append(Paragraph(f"Generated on {date.today()} - School Management App", styles['Normal']))
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def crud_bar(entity_label, df, id_col="id"):
    """Reusable Edit/Delete UI - returns selected id"""
    if df.empty:
        return None
    return st.selectbox(f"Select {entity_label} to Edit / Delete", df[id_col].tolist(), key=f"sel_{entity_label}")

# LOGIN
if "school_id" not in st.session_state and "is_super" not in st.session_state:
    st.title("🏫 School Management - ERP Management System")
    tab1, tab2 = st.tabs(["🏫 School Login","👑 Super Admin"])
    with tab1:
        code=st.text_input("School Code (e.g. RATO01)"); pwd=st.text_input("Password", type="password")
        if st.button("Login as School", use_container_width=True):
            conn=get_conn(); row=conn.execute("SELECT * FROM schools WHERE login_code=? AND password=?", (code.strip(), pwd)).fetchone(); conn.close()
            if row:
                try: exp=date.fromisoformat(row["expiry_date"])
                except: exp=date.today()+timedelta(days=30)
                if date.today()>exp: st.error(f"❌ Plan Expired on {exp}. Pay Rs. {row['monthly_charge']} - JazzCash: 0300-1234567")
                else:
                    st.session_state.school_id=row["id"]; st.session_state.school_name=row["school_name"]; st.session_state.expiry=row["expiry_date"]; st.rerun()
            else: st.error("Wrong Code/Password. Demo: RATO01 / 1234")
        # st.info("Demo: **RATO01 / 1234** | **LARK02 / 5678**")
    with tab2:
        u=st.text_input("Admin Username"); p=st.text_input("Admin Password", type="password")
        if st.button("Login Super Admin"):
            if u=="admin" and p=="admin123": st.session_state.is_super=True; st.rerun()
            else: st.error("Use admin / admin123")
    st.stop()

# SUPER ADMIN - CRUD for Schools
if st.session_state.get("is_super"):
    st.title("👑 Super Admin - Schools CRUD")
    if st.button("Logout"): del st.session_state.is_super; st.rerun()
    st.subheader("➕ Add School")
    with st.form("new_school", clear_on_submit=True):
        c1,c2,c3=st.columns(3)
        with c1: sname=st.text_input("School Name"); scode=st.text_input("Login Code")
        with c2: spass=st.text_input("Password", value="1234"); city=st.text_input("City")
        with c3: phone=st.text_input("Phone"); plan=st.selectbox("Plan", ["Basic","Standard","Premium"])
        charge={"Basic":1500,"Standard":2500,"Premium":4000}[plan]
        exp_days=st.number_input("Days", value=30)
        if st.form_submit_button("Create School"):
            conn=get_conn()
            try:
                exp=(date.today()+timedelta(days=int(exp_days))).isoformat()
                conn.execute("INSERT INTO schools (school_name, login_code, password, city, phone, plan, monthly_charge, expiry_date, payment_status) VALUES (?,?,?,?,?,?,?,?,?)",(sname,scode,spass,city,phone,plan,charge,exp,"Paid")); conn.commit(); st.success(f"Created {scode} - Rs.{charge}/month")
            except Exception as e: st.error(f"Code exists: {e}")
            conn.close()
    conn=get_conn(); df=pd.read_sql("SELECT * FROM schools ORDER BY id", conn); conn.close()
    st.subheader("📋 All Schools - Edit / Delete")
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        df["label"]=df["id"].astype(str)+" - "+df["school_name"]+" ("+df["login_code"]+")"
        sel=st.selectbox("Select School to Edit/Delete", df["label"].tolist())
        sid=int(sel.split(" - ")[0]); row=df[df["id"]==sid].iloc[0]
        with st.form("edit_school"):
            c1,c2,c3=st.columns(3)
            with c1: ename=st.text_input("School Name", value=row["school_name"]); ecode=st.text_input("Code", value=row["login_code"])
            with c2: epass=st.text_input("Password", value=row["password"]); ecity=st.text_input("City", value=str(row["city"] or ""))
            with c3: eplan=st.selectbox("Plan", ["Basic","Standard","Premium"], index=["Basic","Standard","Premium"].index(row["plan"])); echarge=st.number_input("Monthly Charge", value=int(row["monthly_charge"])); eexp=st.text_input("Expiry Date YYYY-MM-DD", value=row["expiry_date"])
            c1,c2=st.columns(2)
            with c1: upd=st.form_submit_button("✅ Update School")
            with c2: dele=st.form_submit_button("🗑️ Delete School")
            if upd:
                conn=get_conn(); conn.execute("UPDATE schools SET school_name=?, login_code=?, password=?, city=?, plan=?, monthly_charge=?, expiry_date=? WHERE id=?", (ename,ecode,epass,ecity,eplan,echarge,eexp,sid)); conn.commit(); conn.close(); st.success("Updated"); st.rerun()
            if dele:
                conn=get_conn(); conn.execute("DELETE FROM schools WHERE id=?", (sid,)); conn.execute("DELETE FROM students WHERE school_id=?", (sid,)); conn.execute("DELETE FROM fees WHERE school_id=?", (sid,)); conn.execute("DELETE FROM cashbook WHERE school_id=?", (sid,)); conn.commit(); conn.close(); st.warning("Deleted"); st.rerun()
        # PDF for schools
        pdf=make_pdf("All Schools Report", ["ID","School","Code","City","Plan","Charge","Expiry"], df[["id","school_name","login_code","city","plan","monthly_charge","expiry_date"]].values.tolist())
        if pdf: st.download_button("📄 Download Schools PDF", pdf, "schools.pdf", "application/pdf")
    # --- SUPER ADMIN ONLY: USERS CRUD FOR ANY SCHOOL ---
    st.divider()
    st.subheader("👥 Users CRUD - Only Super Admin (Admin) Can Create Users")
    st.caption("School cannot create users. Only Admin creates / edits / deletes users for any school.")
    conn2=get_conn(); schools_df=pd.read_sql("SELECT id, school_name, login_code FROM schools ORDER BY id", conn2); conn2.close()
    if not schools_df.empty:
        schools_df["label"]=schools_df["id"].astype(str)+" - "+schools_df["school_name"]+" ("+schools_df["login_code"]+")"
        sel_school=st.selectbox("Select School for User Management", schools_df["label"].tolist(), key="admin_user_school")
        target_school_id=int(sel_school.split(" - ")[0])
        target_school_name=sel_school
        with st.form("admin_add_user", clear_on_submit=True):
            c1,c2,c3=st.columns(3)
            with c1: uname=st.text_input("User Name *")
            with c2: role=st.selectbox("Role", ["school_admin","teacher","accountant"])
            with c3: username=st.text_input("Username *")
            pwd=st.text_input("Password", type="password")
            if st.form_submit_button("➕ Create User (Admin Only)"):
                if uname and username and pwd:
                    c=get_conn(); c.execute("INSERT INTO users (school_id, name, role, username, password) VALUES (?,?,?,?,?)",(target_school_id,uname,role,username,pwd)); c.commit(); c.close(); st.success(f"User {username} created for {target_school_name}"); st.rerun()
                else: st.error("Name, Username and Password required")
        conn2=get_conn(); udf=pd.read_sql("SELECT * FROM users WHERE school_id=? ORDER BY id", conn2, params=(target_school_id,)); conn2.close()
        st.dataframe(udf, use_container_width=True)
        if not udf.empty:
            udf["label"]=udf["id"].astype(str)+" - "+udf["name"]+" ("+udf["username"]+") - "+udf["role"]
            usel=st.selectbox("Select User to Edit / Delete", udf["label"].tolist(), key="admin_user_sel")
            uid=int(usel.split(" - ")[0]); urow=udf[udf["id"]==uid].iloc[0]
            with st.form("admin_edit_user"):
                c1,c2=st.columns(2)
                with c1: ename=st.text_input("Name", value=urow["name"]); erole=st.selectbox("Role", ["school_admin","teacher","accountant"], index=["school_admin","teacher","accountant"].index(urow["role"]) if urow["role"] in ["school_admin","teacher","accountant"] else 0)
                with c2: euser=st.text_input("Username", value=urow["username"]); epass=st.text_input("Password", value=urow["password"])
                a,b=st.columns(2)
                with a: upd=st.form_submit_button("✅ Update User")
                with b: dele=st.form_submit_button("🗑️ Delete User")
                if upd:
                    c=get_conn(); c.execute("UPDATE users SET name=?, role=?, username=?, password=? WHERE id=?", (ename,erole,euser,epass,uid)); c.commit(); c.close(); st.success("User Updated"); st.rerun()
                if dele:
                    c=get_conn(); c.execute("DELETE FROM users WHERE id=?", (uid,)); c.commit(); c.close(); st.warning("User Deleted"); st.rerun()
            pdf2=make_pdf(f"Users - {target_school_name}", ["Name","Role","Username"], udf[["name","role","username"]].values.tolist())
            if pdf2: st.download_button("📄 Download Users PDF", pdf2, "users_admin.pdf", "application/pdf")
    st.stop()

# SCHOOL APP
school_id=st.session_state.school_id; school_name=st.session_state.school_name
with st.sidebar:
    st.title(f"🏫 {school_name}")
    st.caption(f"Expiry: {st.session_state.get('expiry')}")
    menu=st.radio("Menu", ["📊 Dashboard","📈 Data Analysis","👨‍🎓 Students","💰 Collect Fee","🚨 Defaulter List","📒 Cashbook","💸 Expenses","💵 Income","🔑 Change Password"])
    if st.button("Logout"): del st.session_state.school_id; st.rerun()

conn=get_conn()
total_students=conn.execute("SELECT COUNT(*) FROM students WHERE school_id=?", (school_id,)).fetchone()[0]
total_income=conn.execute("SELECT IFNULL(SUM(gross_amount),0) FROM cashbook WHERE school_id=? AND type='income'", (school_id,)).fetchone()[0]
total_expense=conn.execute("SELECT IFNULL(SUM(gross_amount),0) FROM cashbook WHERE school_id=? AND type='expense'", (school_id,)).fetchone()[0]
cash_in_hand=total_income-total_expense
today_str=date.today().isoformat()
today_income=conn.execute("SELECT IFNULL(SUM(gross_amount),0) FROM cashbook WHERE school_id=? AND date=? AND type='income'", (school_id, today_str)).fetchone()[0]
today_expense=conn.execute("SELECT IFNULL(SUM(gross_amount),0) FROM cashbook WHERE school_id=? AND date=? AND type='expense'", (school_id, today_str)).fetchone()[0]
conn.close()

if menu=="📊 Dashboard":
    st.title(f"Dashboard - {school_name}")
    c1,c2,c3,c4=st.columns(4); c1.metric("Total Students", total_students); c2.metric("Today Income", f"Rs. {today_income}"); c3.metric("Today Expense", f"Rs. {today_expense}"); c4.metric("Cash In Hand", f"Rs. {cash_in_hand}")
    conn=get_conn(); df=pd.read_sql("SELECT date, type, gross_amount, description FROM cashbook WHERE school_id=? ORDER BY id DESC LIMIT 10", conn, params=(school_id,)); conn.close()
    st.subheader("Recent Cashbook"); st.dataframe(df, use_container_width=True)
    pdf=make_pdf(f"Dashboard Report - {school_name}", ["Date","Type","Amount","Description"], df.values.tolist())
    if pdf: st.download_button("📄 Download Dashboard PDF", pdf, "dashboard.pdf", "application/pdf")

elif menu=="📈 Data Analysis":
    st.title("📈 Data Analysis")
    conn=get_conn()
    fees_df=pd.read_sql("SELECT * FROM fees WHERE school_id=?", conn, params=(school_id,))
    exp_df=pd.read_sql("SELECT * FROM expenses WHERE school_id=?", conn, params=(school_id,))
    stu_df=pd.read_sql("SELECT * FROM students WHERE school_id=?", conn, params=(school_id,))
    cash_df=pd.read_sql("SELECT * FROM cashbook WHERE school_id=?", conn, params=(school_id,))
    conn.close()
    # 1. Fees per Month
    st.subheader("1️⃣ Fees Collected Per Month")
    if not fees_df.empty:
        g=fees_df.groupby("month")[["paid_fee","due_fee"]].sum().reset_index()
        st.bar_chart(g.set_index("month"))
        st.dataframe(g, use_container_width=True)
    else: st.info("No fee data yet")
    # 2. Students per Class
    st.subheader("2️⃣ Students Per Class")
    if not stu_df.empty:
        g2=stu_df.groupby("class").size().reset_index(name="count")
        st.bar_chart(g2.set_index("class")); st.dataframe(g2, use_container_width=True)
    # 3. Expenses per Category
    st.subheader("3️⃣ Expenses Per Category")
    if not exp_df.empty:
        g3=exp_df.groupby("category")["amount"].sum().reset_index()
        st.bar_chart(g3.set_index("category")); st.dataframe(g3, use_container_width=True)
    # 4. Income vs Expense Trend
    st.subheader("4️⃣ Income vs Expense Trend (Cashbook)")
    if not cash_df.empty:
        g4=cash_df.groupby(["date","type"])["gross_amount"].sum().unstack(fill_value=0).reset_index()
        st.line_chart(g4.set_index("date"))
        st.dataframe(g4, use_container_width=True)
    # 5. Collection Rate
    st.subheader("5️⃣ Collection Rate")
    if not fees_df.empty:
        total_monthly=fees_df["monthly_fee"].sum(); total_paid=fees_df["paid_fee"].sum(); total_due=fees_df["due_fee"].sum()
        rate = (total_paid/total_monthly*100) if total_monthly else 0
        c1,c2,c3,c4=st.columns(4); c1.metric("Expected Fees", f"Rs. {total_monthly}"); c2.metric("Collected", f"Rs. {total_paid}"); c3.metric("Due", f"Rs. {total_due}"); c4.metric("Collection %", f"{rate:.1f}%")
        st.progress(min(rate/100,1.0))
    # PDF Full Analysis
    if not fees_df.empty:
        pdf=make_pdf(f"Data Analysis - {school_name}", ["Month","Paid","Due"], fees_df.groupby("month")[["paid_fee","due_fee"]].sum().reset_index().values.tolist())
        if pdf: st.download_button("📄 Download Analysis PDF", pdf, "analysis.pdf", "application/pdf")

elif menu=="👨‍🎓 Students":
    st.title("Students - Full CRUD")
    with st.form("add_student", clear_on_submit=True):
        c1,c2,c3=st.columns(3)
        with c1: gr=st.text_input("GR No *"); name=st.text_input("Name *")
        with c2: father=st.text_input("Father *"); surname=st.text_input("Surname")
        with c3: cls=st.selectbox("Class", CLASSES); fee=st.number_input("Monthly Fee", min_value=0, value=2000)
        if st.form_submit_button("➕ Add Student"):
            if gr and name:
                conn=get_conn(); conn.execute("INSERT INTO students (school_id, gr, name, father, surname, class, monthly_fee) VALUES (?,?,?,?,?,?,?)",(school_id,gr,name,father,surname,cls,fee)); conn.commit(); conn.close(); st.success("Added"); st.rerun()
            else: st.error("GR and Name required")
    conn=get_conn(); df=pd.read_sql("SELECT * FROM students WHERE school_id=? ORDER BY class, gr", conn, params=(school_id,)); conn.close()
    st.subheader(f"All Students ({len(df)})")
    st.dataframe(df[["id","gr","name","father","surname","class","monthly_fee"]] if not df.empty else df, use_container_width=True)
    if not df.empty:
        df["label"]=df["id"].astype(str)+" - GR "+df["gr"].astype(str)+" - "+df["name"]
        sel=st.selectbox("Select Student to Edit / Delete", df["label"].tolist())
        sid=int(sel.split(" - ")[0]); row=df[df["id"]==sid].iloc[0]
        with st.form("edit_student"):
            c1,c2,c3=st.columns(3)
            with c1: egr=st.text_input("GR", value=row["gr"]); ename=st.text_input("Name", value=row["name"])
            with c2: efather=st.text_input("Father", value=row["father"]); esurname=st.text_input("Surname", value=str(row["surname"] or ""))
            with c3: ecls=st.selectbox("Class", CLASSES, index=CLASSES.index(row["class"]) if row["class"] in CLASSES else 0); efee=st.number_input("Monthly Fee", value=int(row["monthly_fee"]))
            a,b=st.columns(2)
            with a: upd=st.form_submit_button("✅ Update")
            with b: dele=st.form_submit_button("🗑️ Delete")
            if upd:
                conn=get_conn(); conn.execute("UPDATE students SET gr=?, name=?, father=?, surname=?, class=?, monthly_fee=? WHERE id=? AND school_id=?", (egr,ename,efather,esurname,ecls,efee,sid,school_id)); conn.commit(); conn.close(); st.success("Updated"); st.rerun()
            if dele:
                conn=get_conn(); conn.execute("DELETE FROM students WHERE id=? AND school_id=?", (sid,school_id)); conn.execute("DELETE FROM fees WHERE student_id=? AND school_id=?", (sid,school_id)); conn.commit(); conn.close(); st.warning("Deleted"); st.rerun()
        pdf=make_pdf(f"Students List - {school_name}", ["GR","Name","Father","Surname","Class","Fee"], df[["gr","name","father","surname","class","monthly_fee"]].values.tolist())
        if pdf: st.download_button("📄 Download Students PDF", pdf, "students.pdf", "application/pdf")
        st.download_button("⬇️ Download Students CSV", df.to_csv(index=False), "students.csv")

elif menu=="💰 Collect Fee":
    st.title("Collect Fee - Full CRUD")
    conn=get_conn(); students=pd.read_sql("SELECT * FROM students WHERE school_id=? ORDER BY gr", conn, params=(school_id,)); conn.close()
    if students.empty: st.warning("No students yet")
    else:
        students["label"]=students["gr"].astype(str)+" - "+students["name"]+" ("+students["class"]+")"
        sel=st.selectbox("Select Student", students["label"].tolist())
        row=students[students["label"]==sel].iloc[0]
        st.info(f"**{row['name']}** | Father: {row['father']} | Class: {row['class']} | Monthly Fee: Rs. {row['monthly_fee']}")
        with st.form("fee_form", clear_on_submit=True):
            c1,c2,c3=st.columns(3)
            with c1: month=st.selectbox("Month", MONTHS, index=10)
            with c2: paid=st.number_input("Paid Fee", min_value=0, value=int(row["monthly_fee"]))
            with c3: mfee=st.number_input("Monthly Fee", min_value=0, value=int(row["monthly_fee"]))
            due=mfee-paid; st.write(f"Due (Auto): Rs. {due} | Date: {date.today()}")
            if st.form_submit_button("💰 Save Fee"):
                conn=get_conn(); already=conn.execute("SELECT * FROM fees WHERE school_id=? AND student_id=? AND month=?", (school_id, int(row["id"]), month)).fetchone()
                if already: st.error(f"Already paid for {month}")
                else:
                    conn.execute("INSERT INTO fees (school_id, student_id, month, monthly_fee, paid_fee, due_fee, submit_date) VALUES (?,?,?,?,?,?,?)",(school_id, int(row["id"]), month, mfee, paid, due, date.today().isoformat()))
                    conn.execute("INSERT INTO cashbook (school_id, date, type, gross_amount, description) VALUES (?,?, 'income', ?, ?)",(school_id, date.today().isoformat(), paid, f"Fee {month} - {row['name']} GR {row['gr']}")); conn.commit(); st.success("Saved + Added to Cashbook")
                conn.close()
        # List + Edit/Delete Fees
        conn=get_conn(); fdf=pd.read_sql("SELECT * FROM fees WHERE school_id=? AND student_id=? ORDER BY id DESC", conn, params=(school_id, int(row["id"]))); conn.close()
        st.subheader("Fee History - Edit / Delete")
        st.dataframe(fdf, use_container_width=True)
        if not fdf.empty:
            fdf["label"]=fdf["id"].astype(str)+" - "+fdf["month"]+" - Paid "+fdf["paid_fee"].astype(str)
            fsel=st.selectbox("Select Fee to Edit/Delete", fdf["label"].tolist())
            fid=int(fsel.split(" - ")[0]); frow=fdf[fdf["id"]==fid].iloc[0]
            with st.form("edit_fee"):
                c1,c2,c3=st.columns(3)
                with c1: emonth=st.selectbox("Month", MONTHS, index=MONTHS.index(frow["month"]) if frow["month"] in MONTHS else 0)
                with c2: epaid=st.number_input("Paid Fee", value=int(frow["paid_fee"]))
                with c3: emfee=st.number_input("Monthly Fee", value=int(frow["monthly_fee"]))
                edue=emfee-epaid; st.write(f"New Due: Rs. {edue}")
                a,b=st.columns(2)
                with a: upd=st.form_submit_button("✅ Update Fee")
                with b: dele=st.form_submit_button("🗑️ Delete Fee")
                if upd:
                    conn=get_conn(); conn.execute("UPDATE fees SET month=?, monthly_fee=?, paid_fee=?, due_fee=? WHERE id=? AND school_id=?", (emonth,emfee,epaid,edue,fid,school_id)); conn.commit(); conn.close(); st.success("Fee Updated (Cashbook not auto-changed - adjust in Cashbook if needed)"); st.rerun()
                if dele:
                    conn=get_conn(); conn.execute("DELETE FROM fees WHERE id=? AND school_id=?", (fid,school_id)); conn.commit(); conn.close(); st.warning("Fee Deleted"); st.rerun()
            pdf=make_pdf(f"Fee Receipt - {row['name']} GR {row['gr']}", ["Month","Monthly","Paid","Due","Date"], fdf[["month","monthly_fee","paid_fee","due_fee","submit_date"]].values.tolist())
            if pdf: st.download_button("📄 Download Fee Receipt PDF", pdf, f"fee_{row['gr']}.pdf", "application/pdf")

elif menu=="🚨 Defaulter List":
    st.title("Defaulter List - Classwise & Monthwise")
    c1,c2=st.columns(2)
    with c1: fclass=st.selectbox("Class", ["All"]+CLASSES)
    with c2: fmonth=st.selectbox("Month", MONTHS, index=10)
    query="SELECT s.gr, s.name, s.father, s.surname, s.class, s.monthly_fee, IFNULL(f.paid_fee,0) as paid_fee, s.monthly_fee-IFNULL(f.paid_fee,0) as due_fee, CASE WHEN f.paid_fee IS NULL THEN 'Not Paid' ELSE 'Partial Paid' END as status FROM students s LEFT JOIN fees f ON s.id=f.student_id AND f.month=? AND f.school_id=? WHERE s.school_id=? AND (f.id IS NULL OR f.due_fee>0)"
    params=[fmonth, school_id, school_id]
    if fclass!="All": query+=" AND s.class=?"; params.append(fclass)
    query+=" ORDER BY s.class, s.gr"
    conn=get_conn(); df=pd.read_sql(query, conn, params=params); conn.close()
    c1,c2,c3=st.columns(3); c1.metric("Defaulters", len(df)); c2.metric("Total Due", f"Rs. {df['due_fee'].sum() if not df.empty else 0}"); c3.metric("Month", fmonth)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        st.download_button("⬇️ Download CSV", df.to_csv(index=False), f"defaulter_{fclass}_{fmonth}.csv")
        pdf=make_pdf(f"Defaulter List - {school_name} - {fclass} - {fmonth}", ["GR","Name","Father","Surname","Class","Monthly","Paid","Due","Status"], df.values.tolist())
        if pdf: st.download_button("📄 Download Defaulter PDF", pdf, "defaulter.pdf", "application/pdf")

elif menu=="📒 Cashbook":
    st.title("Cashbook - Full CRUD")
    sel_date=st.date_input("Select Date", value=date.today())
    conn=get_conn(); df=pd.read_sql("SELECT * FROM cashbook WHERE school_id=? AND date=? ORDER BY id", conn, params=(school_id, sel_date.isoformat())); all_df=pd.read_sql("SELECT * FROM cashbook WHERE school_id=? ORDER BY id DESC LIMIT 100", conn, params=(school_id,)); conn.close()
    c1,c2,c3=st.columns(3)
    inc=df[df["type"]=="income"]["gross_amount"].sum() if not df.empty else 0; exp=df[df["type"]=="expense"]["gross_amount"].sum() if not df.empty else 0
    c1.metric(f"Income {sel_date}", f"Rs. {inc}"); c2.metric(f"Expense {sel_date}", f"Rs. {exp}"); c3.metric("Net", f"Rs. {inc-exp}")
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        df["label"]=df["id"].astype(str)+" - "+df["type"]+" Rs."+df["gross_amount"].astype(str)+" - "+df["description"].astype(str)
        sel=st.selectbox("Select Cashbook Entry to Edit/Delete", df["label"].tolist())
        cid=int(sel.split(" - ")[0]); row=df[df["id"]==cid].iloc[0]
        with st.form("edit_cash"):
            c1,c2=st.columns(2)
            with c1: etype=st.selectbox("Type", ["income","expense"], index=0 if row["type"]=="income" else 1); eamt=st.number_input("Amount", value=int(row["gross_amount"]))
            with c2: edesc=st.text_input("Description", value=row["description"]); edate=st.text_input("Date YYYY-MM-DD", value=row["date"])
            a,b=st.columns(2)
            with a: upd=st.form_submit_button("✅ Update")
            with b: dele=st.form_submit_button("🗑️ Delete")
            if upd:
                conn=get_conn(); conn.execute("UPDATE cashbook SET type=?, gross_amount=?, description=?, date=? WHERE id=? AND school_id=?", (etype,eamt,edesc,edate,cid,school_id)); conn.commit(); conn.close(); st.success("Updated"); st.rerun()
            if dele:
                conn=get_conn(); conn.execute("DELETE FROM cashbook WHERE id=? AND school_id=?", (cid,school_id)); conn.commit(); conn.close(); st.warning("Deleted"); st.rerun()
        pdf=make_pdf(f"Cashbook - {school_name} - {sel_date}", ["Date","Type","Amount","Description"], df[["date","type","gross_amount","description"]].values.tolist())
        if pdf: st.download_button("📄 Download Cashbook PDF", pdf, "cashbook.pdf", "application/pdf")

elif menu=="💸 Expenses":
    st.title("Expenses - Full CRUD")
    with st.form("exp_form", clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1: cat=st.selectbox("Category", ["Salary","Electricity","Repair","Books","Stationery","Transport","Rent","Other"])
        with c2: amt=st.number_input("Amount", min_value=0)
        desc=st.text_input("Description"); exp_date=st.date_input("Date", value=date.today())
        if st.form_submit_button("➕ Add Expense"):
            conn=get_conn(); conn.execute("INSERT INTO expenses (school_id, date, category, amount, description) VALUES (?,?,?,?,?)",(school_id, exp_date.isoformat(), cat, amt, desc)); conn.execute("INSERT INTO cashbook (school_id, date, type, gross_amount, description) VALUES (?,?, 'expense', ?, ?)",(school_id, exp_date.isoformat(), amt, f"Expense - {cat} - {desc}")); conn.commit(); conn.close(); st.success("Saved + Cashbook"); st.rerun()
    conn=get_conn(); df=pd.read_sql("SELECT * FROM expenses WHERE school_id=? ORDER BY id DESC LIMIT 50", conn, params=(school_id,)); conn.close()
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        df["label"]=df["id"].astype(str)+" - "+df["category"]+" Rs."+df["amount"].astype(str)
        sel=st.selectbox("Select Expense to Edit/Delete", df["label"].tolist())
        eid=int(sel.split(" - ")[0]); row=df[df["id"]==eid].iloc[0]
        with st.form("edit_exp"):
            c1,c2=st.columns(2)
            with c1: ecat=st.selectbox("Category", ["Salary","Electricity","Repair","Books","Stationery","Transport","Rent","Other"], index=["Salary","Electricity","Repair","Books","Stationery","Transport","Rent","Other"].index(row["category"]) if row["category"] in ["Salary","Electricity","Repair","Books","Stationery","Transport","Rent","Other"] else 0); eamt=st.number_input("Amount", value=int(row["amount"]))
            with c2: edesc=st.text_input("Description", value=row["description"]); edate=st.text_input("Date", value=row["date"])
            a,b=st.columns(2)
            with a: upd=st.form_submit_button("✅ Update")
            with b: dele=st.form_submit_button("🗑️ Delete")
            if upd:
                conn=get_conn(); conn.execute("UPDATE expenses SET category=?, amount=?, description=?, date=? WHERE id=? AND school_id=?", (ecat,eamt,edesc,edate,eid,school_id)); conn.commit(); conn.close(); st.success("Updated"); st.rerun()
            if dele:
                conn=get_conn(); conn.execute("DELETE FROM expenses WHERE id=? AND school_id=?", (eid,school_id)); conn.commit(); conn.close(); st.warning("Deleted - Note: Cashbook entry remains, delete it in Cashbook if needed"); st.rerun()
        pdf=make_pdf(f"Expenses - {school_name}", ["Date","Category","Amount","Description"], df[["date","category","amount","description"]].values.tolist())
        if pdf: st.download_button("📄 Download Expenses PDF", pdf, "expenses.pdf", "application/pdf")

elif menu=="💵 Income":
    st.title("Other Income - Full CRUD")
    st.caption("Fees go to Cashbook automatically. Use this for Donation, Admission, Grant.")
    with st.form("inc_form", clear_on_submit=True):
        c1,c2=st.columns(2)
        with c1: src=st.selectbox("Source", ["Donation","Admission Fee","Govt Grant","Rent","Other"])
        with c2: amt=st.number_input("Amount", min_value=0)
        desc=st.text_input("Description"); inc_date=st.date_input("Date", value=date.today())
        if st.form_submit_button("➕ Add Income"):
            conn=get_conn(); conn.execute("INSERT INTO income (school_id, date, source, amount, description) VALUES (?,?,?,?,?)",(school_id, inc_date.isoformat(), src, amt, desc)); conn.execute("INSERT INTO cashbook (school_id, date, type, gross_amount, description) VALUES (?,?, 'income', ?, ?)",(school_id, inc_date.isoformat(), amt, f"Income - {src} - {desc}")); conn.commit(); conn.close(); st.success("Saved + Cashbook"); st.rerun()
    conn=get_conn(); df=pd.read_sql("SELECT * FROM income WHERE school_id=? ORDER BY id DESC LIMIT 50", conn, params=(school_id,)); conn.close()
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        df["label"]=df["id"].astype(str)+" - "+df["source"]+" Rs."+df["amount"].astype(str)
        sel=st.selectbox("Select Income to Edit/Delete", df["label"].tolist())
        iid=int(sel.split(" - ")[0]); row=df[df["id"]==iid].iloc[0]
        with st.form("edit_inc"):
            c1,c2=st.columns(2)
            with c1: esrc=st.selectbox("Source", ["Donation","Admission Fee","Govt Grant","Rent","Other"], index=["Donation","Admission Fee","Govt Grant","Rent","Other"].index(row["source"]) if row["source"] in ["Donation","Admission Fee","Govt Grant","Rent","Other"] else 0); eamt=st.number_input("Amount", value=int(row["amount"]))
            with c2: edesc=st.text_input("Description", value=row["description"]); edate=st.text_input("Date", value=row["date"])
            a,b=st.columns(2)
            with a: upd=st.form_submit_button("✅ Update")
            with b: dele=st.form_submit_button("🗑️ Delete")
            if upd:
                conn=get_conn(); conn.execute("UPDATE income SET source=?, amount=?, description=?, date=? WHERE id=? AND school_id=?", (esrc,eamt,edesc,edate,iid,school_id)); conn.commit(); conn.close(); st.success("Updated"); st.rerun()
            if dele:
                conn=get_conn(); conn.execute("DELETE FROM income WHERE id=? AND school_id=?", (iid,school_id)); conn.commit(); conn.close(); st.warning("Deleted"); st.rerun()
        pdf=make_pdf(f"Income - {school_name}", ["Date","Source","Amount","Description"], df[["date","source","amount","description"]].values.tolist())
        if pdf: st.download_button("📄 Download Income PDF", pdf, "income.pdf", "application/pdf")

elif menu=="🔑 Change Password":
    st.title("🔑 Change My School Password")
    st.info(f"School: **{school_name}** | Code: You are logged in as this school. You can ONLY change your OWN password. You CANNOT create / edit / delete users. Only Super Admin can do Users CRUD.")
    st.warning("⚠️ Users Management is disabled for schools. If you need a new teacher / accountant user, contact Admin on WhatsApp. Admin will create it for you.")
    with st.form("change_pass"):
        old_pass = st.text_input("Current Password", type="password")
        new_pass = st.text_input("New Password", type="password")
        confirm_pass = st.text_input("Confirm New Password", type="password")
        if st.form_submit_button("✅ Change My Password"):
            if not old_pass or not new_pass:
                st.error("Fill all fields")
            elif new_pass != confirm_pass:
                st.error("New Password and Confirm do not match")
            elif len(new_pass) < 4:
                st.error("Password must be at least 4 characters")
            else:
                conn=get_conn()
                row=conn.execute("SELECT password FROM schools WHERE id=?", (school_id,)).fetchone()
                if row and row["password"] != old_pass:
                    st.error("Current Password is wrong!")
                else:
                    conn.execute("UPDATE schools SET password=? WHERE id=?", (new_pass, school_id))
                    conn.commit(); st.success("✅ Your password changed successfully! Please login again with new password.")
                conn.close()
    st.caption("After changing password, logout and login with new password.")
