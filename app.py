import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
from datetime import date, datetime
import plotly.express as px
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from prophet import Prophet
from fpdf import FPDF

st.set_page_config(page_title="Small Business Sales & Profit Analyzer", layout="wide")

# ================= DATABASE =================

conn = sqlite3.connect("business.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
username TEXT PRIMARY KEY,
password TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS business(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
business_name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
business_name TEXT,
product_name TEXT,
quantity INTEGER,
price REAL,
date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
business_name TEXT,
expense_name TEXT,
category TEXT,
amount REAL,
date TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
business_name TEXT,
product_name TEXT,
stock INTEGER,
cogs REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS login_logs(
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
login_time TEXT,
logout_time TEXT,
duration_minutes REAL
)
""")

conn.commit()

# ================= SESSION =================


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "active_business" not in st.session_state:
    st.session_state.active_business = None

if "admin_pass" not in st.session_state:
    st.session_state.admin_pass = "admin123"

if "business_switched" not in st.session_state:
    st.session_state.business_switched = False

# ================= LOGIN =================

if not st.session_state.logged_in:

    st.title("Small Business Sales & Profit Analyzer")

    option = st.radio("Auth",["Login","Register"],horizontal=True,label_visibility="collapsed")

    user = st.text_input("Username")
    pwd = st.text_input("Password",type="password")

    if option == "Login":

        if st.button("Login"):

            cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (user,pwd))

            if cursor.fetchone():

                st.session_state.logged_in = True
                st.session_state.username = user

                login_time = datetime.now()

                cursor.execute("INSERT INTO login_logs(username,login_time) VALUES (?,?)",(user,str(login_time)))
                conn.commit()

                st.session_state.login_time = login_time

                st.rerun()

            else:
                st.error("Invalid Credentials")

    else:

        if st.button("Register"):

            try:

                cursor.execute("INSERT INTO users VALUES (?,?)",(user,pwd))
                conn.commit()

                st.success("Account Created")

            except:

                st.error("Username already exists")

# ================= MAIN APP =================

else:

    with st.sidebar:

        st.markdown(f"### 👤 {st.session_state.username}")

    
        if st.session_state.active_business:
            st.success(f" Using Business: {st.session_state.active_business}")
        else:
            st.warning("⚠ No Business Selected")

        menu = st.radio("Navigation",[
            "Business",
            "Dashboard",
            "Sales",
            "Expenses",
            "Inventory",
            "Analytics & Forecasting",
            "Reports",
            "Admin Dashboard",
            "Logout"
        ])


# ================= BUSINESS =================

    if menu == "Business":

        st.title("Business Management")

        bname = st.text_input("Business Name")

        if st.button("Add Business"):

            cursor.execute("""
            INSERT INTO business(username,business_name)
            VALUES (?,?)
            """,
            (st.session_state.username,bname))

            conn.commit()

            st.success("Business Added Successfully")

        st.subheader("Your Businesses")

        business_df = pd.read_sql(
            "SELECT * FROM business WHERE username=?",
            conn,
            params=(st.session_state.username,)
        )

        st.dataframe(business_df)

        if not business_df.empty:

            selected_business = st.selectbox(
                "Choose Business to Use",
                business_df["business_name"]
            )

            if st.button("Use This Business"):

                st.session_state.active_business = selected_business

                # reset dashboard numbers when switching business
                st.session_state.business_switched = True

                st.success(f"Now using business: {selected_business}")

                st.rerun()


                
# ================= DASHBOARD =================

    elif menu == "Dashboard":

        st.title("Business Dashboard")

        sales_df = pd.read_sql("""SELECT * FROM sales WHERE username=? AND business_name=?""",
                    conn,
                    params=(st.session_state.username, st.session_state.active_business)
                    )

        exp_df = pd.read_sql("""SELECT * FROM expenses WHERE username=? AND business_name=?""",
                             conn,
                             params=(st.session_state.username, st.session_state.active_business)
                             )

        inv_df = pd.read_sql("""SELECT * FROM inventory WHERE username=? AND business_name=?""",
                             conn,
                             params=(st.session_state.username, st.session_state.active_business)
                             )

        sales_df["revenue"] = sales_df["quantity"] * sales_df["price"]
        sales_df["date"] = pd.to_datetime(sales_df["date"], errors="coerce")

        if st.session_state.business_switched:

            total_sales = 0
            total_expenses = 0
            total_cogs = 0
            profit = 0

        else:

            total_sales = sales_df["revenue"].sum() if not sales_df.empty else 0
            total_expenses = exp_df["amount"].sum() if not exp_df.empty else 0

            total_cogs = 0

            if not inv_df.empty and not sales_df.empty:

                merged = sales_df.merge(inv_df,on="product_name",how="left")

                merged["cogs_total"] = merged["quantity"] * merged["cogs"].fillna(0)

                total_cogs = merged["cogs_total"].sum()

            profit = total_sales - total_expenses - total_cogs

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Revenue",round(total_sales,2))
        c2.metric("Expenses",round(total_expenses,2))
        c3.metric("COGS",round(total_cogs,2))
        c4.metric("Net Profit",round(profit,2))

        st.session_state.business_switched = False

        # ===== DATABASE CHARTS =====

        if not sales_df.empty and not st.session_state.business_switched:

            bar_data = sales_df.groupby("product_name")["revenue"].sum().reset_index()

            st.subheader("Revenue by Product")
            fig_bar = px.bar(bar_data,x="product_name",y="revenue",color="product_name")
            st.plotly_chart(fig_bar,width="stretch")

            # ===== PROFIT MARGIN BY PRODUCT =====

        if not sales_df.empty and not inv_df.empty and not st.session_state.business_switched:

            profit_df = sales_df.merge(inv_df,on="product_name",how="left")

            profit_df["cogs_total"] = profit_df["quantity"] * profit_df["cogs"].fillna(0)
            profit_df["revenue"] = profit_df["quantity"] * profit_df["price"]
            profit_df["profit"] = profit_df["revenue"] - profit_df["cogs_total"]

            profit_summary = profit_df.groupby("product_name").agg({
                "revenue":"sum",
                "profit":"sum"
            }).reset_index()

            profit_summary["profit_margin"] = (
                profit_summary["profit"] / profit_summary["revenue"] * 100
            )

            st.subheader("Profit Margin by Product")

            fig_margin = px.bar(
                profit_summary,
                x="product_name",
                y="profit_margin",
                color="product_name",
                labels={"profit_margin":"Profit Margin (%)"}
            )

            st.plotly_chart(fig_margin,width="stretch")

            st.subheader("Revenue Trend ")
            line_data = sales_df.groupby("date")["revenue"].sum().reset_index()
            fig_line = px.line(line_data,x="date",y="revenue",markers=True)
            st.plotly_chart(fig_line,width="stretch")

            st.subheader("Revenue Distribution ")
            fig_pie = px.pie(bar_data,names="product_name",values="revenue")
            st.plotly_chart(fig_pie,width="stretch")

        if not exp_df.empty and not st.session_state.business_switched:

            st.subheader("Expense Categories ")
            fig2 = px.pie(exp_df,names="category",values="amount")
            st.plotly_chart(fig2,width="stretch")

        # ===== LOW STOCK =====

        if not inv_df.empty:
            low_stock = inv_df[inv_df["stock"] < 5]
            if not low_stock.empty:
                st.warning("⚠ Low Stock Alert")
                st.dataframe(low_stock)

        st.markdown("---")

        # ================= CSV DASHBOARD =================

        st.subheader("Upload CSV for Quick Analysis")

        file = st.file_uploader(
            "Upload CSV (product_name, quantity, price, cogs)",
            type=["csv"]
        )

        if file:

            df = pd.read_csv(file)
            df.columns = df.columns.str.strip().str.lower()

            required = {"product_name","quantity","price","cogs"}

            if not required.issubset(df.columns):
                st.error("CSV must contain product_name, quantity, price, cogs")

            else:

                df["revenue"] = df["quantity"] * df["price"]
                df["total_cogs"] = df["quantity"] * df["cogs"]
                df["profit"] = df["revenue"] - df["total_cogs"]

                st.success("CSV Loaded Successfully")

                c1,c2,c3 = st.columns(3)
                c1.metric("Total Revenue",round(df["revenue"].sum(),2))
                c2.metric("Total COGS",round(df["total_cogs"].sum(),2))
                c3.metric("Total Profit",round(df["profit"].sum(),2))

                bar_csv = df.groupby("product_name")["revenue"].sum().reset_index()

                st.subheader(" Revenue by Product ")
                fig_csv = px.bar(bar_csv,x="product_name",y="revenue",color="product_name")
                st.plotly_chart(fig_csv,width="stretch")

                # ===== PROFIT MARGIN CSV =====

                df["profit_margin"] = (df["profit"] / df["revenue"]) * 100

                margin_csv = df.groupby("product_name")["profit_margin"].mean().reset_index()

                st.subheader("CSV Profit Margin by Product")

                fig_margin_csv = px.bar(
                    margin_csv,
                    x="product_name",
                    y="profit_margin",
                    color="product_name",
                    labels={"profit_margin":"Profit Margin (%)"}
                )

                st.plotly_chart(fig_margin_csv,width="stretch")

                st.subheader(" Revenue Distribution ")
                fig_pie_csv = px.pie(bar_csv,names="product_name",values="revenue")
                st.plotly_chart(fig_pie_csv,width="stretch")

                df["date"] = pd.date_range(start="2024-01-01",periods=len(df))
                line_csv = df.groupby("date")["revenue"].sum().reset_index()

                st.subheader(" Revenue Trend ")
                fig_line_csv = px.line(line_csv,x="date",y="revenue",markers=True)
                st.plotly_chart(fig_line_csv,width="stretch")

    

# ================= SALES =================

    elif menu == "Sales":

        st.title("Sales Management")

        p = st.text_input("Product")
        q = st.number_input("Quantity",min_value=1)
        pr = st.number_input("Price",min_value=0.0)
        d = st.date_input("Date",value=date.today())

        if st.button("Add Sale"):

            cursor.execute("""INSERT INTO sales(username,business_name,product_name,quantity,price,date) VALUES (?,?,?,?,?,?)""",(
                st.session_state.username,
                st.session_state.active_business,
                p,q,pr,str(d)))

            cursor.execute("UPDATE inventory SET stock = stock - ? WHERE username=? AND product_name=?",
                           (q,st.session_state.username,p))

            conn.commit()

            st.success("Sale Added")

        st.dataframe(pd.read_sql("SELECT * FROM sales WHERE username=? AND business_name=?",
                                 conn,
                                 params=(st.session_state.username, st.session_state.active_business)
                                 ))
        
        st.session_state.business_switched = False

# ================= EXPENSES =================

    elif menu == "Expenses":

        st.title("Expense Management")

        name = st.text_input("Expense Name")

        category = st.selectbox("Category",
                                ["Rent","Utilities","Supplies","Transport","Salary","Other"])

        amount = st.number_input("Amount",min_value=0.0)

        d = st.date_input("Date",value=date.today())

        if st.button("Add Expense"):

            cursor.execute("""INSERT INTO expenses(username,business_name,expense_name,category,amount,date) VALUES (?,?,?,?,?,?)""",(
                st.session_state.username,
                st.session_state.active_business,
                name,
                category,
                amount,
                str(d)
                ))

            conn.commit()

            st.success("Expense Added")

        st.dataframe(pd.read_sql("SELECT * FROM expenses WHERE username=? AND business_name=?",
                                 conn,params=(st.session_state.username,st.session_state.active_business)))
        
        st.session_state.business_switched = False

# ================= INVENTORY =================

    elif menu == "Inventory":

        st.title("Inventory")

        p = st.text_input("Product Name")
        s = st.number_input("Stock",min_value=0)
        c = st.number_input("COGS",min_value=0.0)

        if st.button("Add Inventory"):

            cursor.execute("""INSERT INTO inventory(username,business_name,product_name,stock,cogs) VALUES (?,?,?,?,?)""",(
                st.session_state.username,
                st.session_state.active_business,
                p,
                s,
                c
                ))

            conn.commit()

            st.success("Inventory Added")

        inv_df = pd.read_sql("SELECT * FROM inventory WHERE username=? AND business_name=?",
                             conn,
                             params=(st.session_state.username,st.session_state.active_business))

        st.dataframe(inv_df)

        st.session_state.business_switched = False
# ================= ANALYTICS =================

    elif menu == "Analytics & Forecasting":

        st.title("AI Sales Forecasting & Advanced Analytics")

        source = st.radio(
            "Select Data Source",
            ["Use Stored Sales Data", "Upload CSV"]
        )

        # ================= DATA LOADING =================

        if source == "Upload CSV":

            file = st.file_uploader(
                "Upload CSV file (must contain: date, quantity, price)",
                type=["csv"]
            )

            if file is None:
                st.info("Please upload a CSV file.")
                st.stop()

            df = pd.read_csv(file)
            df.columns = df.columns.str.strip().str.lower()

            required = {"date","quantity","price"}

            if not required.issubset(df.columns):
                st.error("CSV must contain columns: date, quantity, price")
                st.stop()

            df["date"] = pd.to_datetime(df["date"])
            df["revenue"] = df["quantity"] * df["price"]

        else:

            df = pd.read_sql("""SELECT * FROM sales WHERE username=? AND business_name=?""",
                             conn,params=(st.session_state.username, st.session_state.active_business)
                             )

            if df.empty:
                st.warning("No sales data available.")
                st.stop()

            df["date"] = pd.to_datetime(df["date"])
            df["revenue"] = df["quantity"] * df["price"]

        # ================= DAILY REVENUE =================

        daily_df = df.groupby("date")["revenue"].sum().reset_index()
        daily_df = daily_df.sort_values("date")

        st.subheader("Daily Revenue Trend")

        fig_daily = px.line(daily_df,x="date",y="revenue",markers=True)
        st.plotly_chart(fig_daily,width="stretch")

        # ================= MONTHLY SUMMARY =================

        df["month"] = df["date"].dt.to_period("M").astype(str)

        monthly = df.groupby("month")["revenue"].sum().reset_index()

        st.subheader("Monthly Revenue Summary")

        fig_month = px.bar(monthly,x="month",y="revenue",color="month")
        st.plotly_chart(fig_month,width="stretch")

        # ================= LINEAR REGRESSION =================

        st.subheader("Linear Regression Forecast")

        daily_df["day"] = np.arange(len(daily_df))

        X = daily_df[["day"]]
        y = daily_df["revenue"]

        model = LinearRegression()
        model.fit(X,y)

        predictions = model.predict(X)

        r2_lr = r2_score(y,predictions)

        future_days = 30

        future_X = np.arange(len(daily_df),len(daily_df)+future_days).reshape(-1,1)

        future_pred = model.predict(future_X)

        future_dates = pd.date_range(
            start=daily_df["date"].max(),
            periods=future_days+1
        )[1:]

        fig_lr = px.line()

        fig_lr.add_scatter(
            x=daily_df["date"],
            y=daily_df["revenue"],
            name="Actual"
        )

        fig_lr.add_scatter(
            x=future_dates,
            y=future_pred,
            name="Predicted"
        )

        st.plotly_chart(fig_lr,width="stretch")

        st.success(f"Linear Regression Accuracy (R²): {round(r2_lr*100,2)}%")

        # ================= PROPHET FORECAST =================

        st.subheader("Prophet Forecast")

        prophet_df = daily_df.rename(columns={"date":"ds","revenue":"y"})

        model = Prophet(
            daily_seasonality=True,
            weekly_seasonality=True,
            yearly_seasonality=True
        )

        model.fit(prophet_df)

        future = model.make_future_dataframe(periods=30)

        forecast = model.predict(future)

        st.subheader("Trend & Seasonality")

        st.pyplot(model.plot_components(forecast))

        st.subheader("Actual vs Predicted Comparison")

        fig_prophet = px.line()

        fig_prophet.add_scatter(
            x=prophet_df["ds"],
            y=prophet_df["y"],
            name="Actual"
        )

        fig_prophet.add_scatter(
            x=forecast["ds"],
            y=forecast["yhat"],
            name="Predicted"
        )

        st.plotly_chart(fig_prophet,width="stretch")

        # ================= PROPHET ACCURACY =================

        merged = prophet_df.merge(
            forecast[["ds","yhat"]],
            on="ds",
            how="inner"
        )

        r2_prophet = r2_score(merged["y"],merged["yhat"])

        st.success(f"Prophet Accuracy (R²): {round(r2_prophet*100,2)}%")

        # ================= NEXT 30 DAYS =================

        st.subheader("Next 30 Days Prediction")

        next_30 = forecast[["ds","yhat","yhat_lower","yhat_upper"]].tail(30)

        st.dataframe(next_30)

        # ================= DOWNLOAD CSV =================

        csv = next_30.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download Forecast CSV",
            data=csv,
            file_name="sales_forecast.csv",
            mime="text/csv"
        )

# ================= REPORTS =================

    elif menu == "Reports":

        st.title("Business Reports")

        sales_df = pd.read_sql("""SELECT * FROM sales WHERE username=? AND business_name=?""",
                               conn,
                               params=(st.session_state.username, st.session_state.active_business)
                               )

        exp_df = pd.read_sql("""SELECT * FROM expenses WHERE username=? AND business_name=?""",
                             conn,
                             params=(st.session_state.username, st.session_state.active_business)
                             )

        inv_df = pd.read_sql("""SELECT * FROM inventory WHERE username=? AND business_name=?""",
                             conn,
                             params=(st.session_state.username, st.session_state.active_business)
                             )

        # ================= SUMMARY =================

        if not sales_df.empty:
            sales_df["revenue"] = sales_df["quantity"] * sales_df["price"]

        total_sales = sales_df["revenue"].sum() if not sales_df.empty else 0
        total_exp = exp_df["amount"].sum() if not exp_df.empty else 0
        profit = total_sales - total_exp

        st.subheader("Financial Summary")

        summary = pd.DataFrame({
            "Metric":["Total Sales","Total Expenses","Net Profit"],
            "Value":[total_sales,total_exp,profit]
        })

        st.dataframe(summary)

        # ================= SALES REPORT =================

        st.subheader("Sales Report")

        if not sales_df.empty:
            st.dataframe(sales_df)
        else:
            st.info("No sales data available")

        # ================= EXPENSE REPORT =================

        st.subheader("Expenses Report")

        if not exp_df.empty:
            st.dataframe(exp_df)
        else:
            st.info("No expenses data available")

        # ================= INVENTORY REPORT =================

        st.subheader("Inventory Report")

        if not inv_df.empty:
            st.dataframe(inv_df)
        else:
            st.info("No inventory data available")

        # ================= EXCEL REPORT =================

        with pd.ExcelWriter("business_report.xlsx") as writer:

            summary.to_excel(writer,sheet_name="Summary",index=False)

            if not sales_df.empty:
                sales_df.to_excel(writer,sheet_name="Sales",index=False)

            if not exp_df.empty:
                exp_df.to_excel(writer,sheet_name="Expenses",index=False)

            if not inv_df.empty:
                inv_df.to_excel(writer,sheet_name="Inventory",index=False)

        with open("business_report.xlsx","rb") as f:

            st.download_button(
                "Download Full Excel Report",
                f,
                "business_report.xlsx"
            )

        # ================= PDF REPORT =================

        if st.button("Generate PDF Report"):

            pdf = FPDF()
            pdf.add_page()

            pdf.set_font("Arial","B",16)
            pdf.cell(200,10,"Business Report",ln=True)

            pdf.set_font("Arial","",12)
            pdf.ln(5)

            pdf.cell(200,10,f"Total Sales: {total_sales}",ln=True)
            pdf.cell(200,10,f"Total Expenses: {total_exp}",ln=True)
            pdf.cell(200,10,f"Net Profit: {profit}",ln=True)

            pdf.ln(10)
            pdf.cell(200,10,"Inventory Overview:",ln=True)

            if not inv_df.empty:
                for i,row in inv_df.iterrows():

                    pdf.cell(
                        200,
                        8,
                        f"{row['product_name']} | Stock:{row['stock']} | COGS:{row['cogs']}",
                        ln=True
                    )

            pdf.output("business_report.pdf")

            with open("business_report.pdf","rb") as f:

                st.download_button(
                    "Download PDF Report",
                    f,
                    "business_report.pdf"
                )


# ================= ADMIN =================

    elif menu == "Admin Dashboard":
        
        st.title("Admin Dashboard Access")

        admin_password = st.text_input("Enter Admin Password", type="password")

        if admin_password != st.session_state.admin_pass:
            st.warning("Enter correct admin password to access dashboard")
            st.stop()

        st.success("Admin Access Granted")

        # ================= ADMIN DASHBOARD =================

        st.title("System Admin Panel")

        users = pd.read_sql("SELECT * FROM users",conn)
        sales = pd.read_sql("SELECT * FROM sales",conn)
        exp = pd.read_sql("SELECT * FROM expenses",conn)

        businesses = pd.read_sql("SELECT * FROM business", conn)

        c1,c2,c3,c4 = st.columns(4)

        c1.metric("Users",len(users))
        c2.metric("Businesses", len(businesses))
        c2.metric("Sales Records",len(sales))
        c3.metric("Expense Records",len(exp))
        

        st.subheader("All Users")
        st.dataframe(users)

        st.subheader("All Businesses")
        st.dataframe(businesses)

        st.subheader("User Login Activity")
        logs = pd.read_sql("SELECT * FROM login_logs",conn)
        st.dataframe(logs)

        st.markdown("---")


        st.subheader("Change User Password")

        # select user
        selected_user = st.selectbox(
            "Select User",
            users["username"]
        )

        new_password = st.text_input("Enter New Password", type="password")

        if st.button("Update User Password"):

            cursor.execute(
                "UPDATE users SET password=? WHERE username=?",
                (new_password, selected_user)
            )

            conn.commit()

            st.success(f"Password updated for user: {selected_user}")

# ================= LOGOUT =================

    elif menu == "Logout":

        logout_time = datetime.now()

        duration = (logout_time - st.session_state.login_time).total_seconds()/60

        cursor.execute("""
        UPDATE login_logs
        SET logout_time=?,duration_minutes=?
        WHERE username=? AND logout_time IS NULL
        """,(str(logout_time),duration,st.session_state.username))

        conn.commit()

        st.session_state.logged_in = False
        st.session_state.username = ""

        st.rerun()