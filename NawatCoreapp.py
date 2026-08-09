from datetime import datetime
import io
import sqlite3
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth

# --- STREAMLIT PAGE CONFIG ---
st.set_page_config(
    page_title="NawatCore - Inventory & Sales Hub",
    layout="wide",
    page_icon="🏢",
)


# --- EXCEL GENERATOR HELPER ---
def generate_excel_bytes(dataframes_dict):
    """Generates an in-memory Excel file containing one or more sheets."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dataframes_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()


# --- 1. USER LOGIN CONFIGURATION (STREAMLIT SECRETS) ---
try:
    credentials = st.secrets["credentials"].to_dict()
except Exception:
    st.error(
        "⚠️ Credentials configuration missing! Please add `[credentials]` to your `.streamlit/secrets.toml` file or Streamlit Cloud Settings."
    )
    st.stop()

# Automatically hash plain-text passwords
stauth.Hasher.hash_passwords(credentials)

# Initialize Authenticator
authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="nawatcore_sales_cookie",
    key="secret_auth_key_12345",
    cookie_expiry_days=30,
)

# --- LOGIN SCREEN HEADER ---
st.title("🏢 NawatCore")
st.caption("Official Inventory & Sales Management Portal")
st.markdown("---")

# Render Login Form
authenticator.login()

# Check Authentication
if st.session_state.get("authentication_status") is False:
    st.error("Username or password is incorrect.")
elif st.session_state.get("authentication_status") is None:
    st.warning("Please enter your credentials to log in to NawatCore.")
elif st.session_state.get("authentication_status"):

    # --- SIDEBAR BRANDING & LOGOUT ---
    st.sidebar.title("🏢 NawatCore")
    st.sidebar.caption("Management Console")
    st.sidebar.write(f"Logged in as: **{st.session_state['name']}**")
    authenticator.logout("Log Out", "sidebar")

    # --- 2. DATABASE SETUP ---
    DB_NAME = "inventory_sales.db"

    def init_db():
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Products Table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                sku TEXT,
                landed_cost REAL NOT NULL,
                default_price REAL NOT NULL,
                stock INTEGER NOT NULL
            )
        """
        )

        # Sales Table
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                quantity INTEGER NOT NULL,
                unit_sale_price REAL NOT NULL,
                gross_total REAL NOT NULL,
                sale_type TEXT NOT NULL,
                shipping_cost REAL DEFAULT 0.0,
                net_total REAL NOT NULL,
                landed_cost_total REAL NOT NULL,
                net_profit REAL NOT NULL,
                payment_method TEXT NOT NULL,
                sale_date TIMESTAMP NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        """
        )
        conn.commit()
        conn.close()

    init_db()

    def get_connection():
        return sqlite3.connect(DB_NAME)

    # --- 3. MAIN APPLICATION HEADER ---
    st.title("📦 NawatCore | Inventory & Sales Management Hub")

    tabs = st.tabs(
        [
            "📊 Dashboard",
            "➕ Manage Inventory",
            "🛒 Log Sales",
            "📜 Sales History",
        ]
    )

    # -------------------------------------------------------------------
    # TAB 1: DASHBOARD & MASTER EXCEL EXPORT
    # -------------------------------------------------------------------
    with tabs[0]:
        st.header("NawatCore Business Overview")
        conn = get_connection()

        products_df = pd.read_sql_query("SELECT * FROM products", conn)
        sales_df = pd.read_sql_query(
            """
            SELECT s.id AS 'Sale ID', s.sale_date AS 'Date & Time', p.name AS 'Product', 
                   s.quantity AS 'Qty', s.unit_sale_price AS 'Sold Price/Unit', 
                   s.gross_total AS 'Gross Rev', s.sale_type AS 'Type', 
                   s.shipping_cost AS 'Shipping Cost', s.net_total AS 'Net Revenue',
                   s.net_profit AS 'Net Profit', s.payment_method AS 'Payment Method'
            FROM sales s 
            JOIN products p ON s.product_id = p.id
            ORDER BY s.sale_date DESC
        """,
            conn,
        )
        conn.close()

        # Key Metrics
        m1, m2, m3, m4 = st.columns(4)
        total_products = len(products_df)
        gross_rev = (
            sales_df["Gross Rev"].sum()
            if not sales_df.empty
            else 0.0
        )
        net_profit = (
            sales_df["Net Profit"].sum()
            if not sales_df.empty
            else 0.0
        )
        low_stock = (
            len(products_df[products_df["stock"] < 5])
            if not products_df.empty
            else 0
        )

        m1.metric("Total Products", total_products)
        m2.metric("Gross Revenue", f"${gross_rev:,.2f}")
        m3.metric("Net Profit", f"${net_profit:,.2f}")
        m4.metric("Low Stock Items (<5)", low_stock)

        st.markdown("---")

        # MASTER EXCEL EXPORT BUTTON
        st.subheader("📥 Export Reports")
        st.write(
            "Download your complete NawatCore data in a single multi-sheet Excel file."
        )

        if not products_df.empty or not sales_df.empty:
            excel_data = generate_excel_bytes(
                {"Inventory": products_df, "Sales Ledger": sales_df}
            )
            st.download_button(
                label="📊 Download Complete NawatCore Excel Report (.xlsx)",
                data=excel_data,
                file_name=f"NawatCore_Full_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        else:
            st.info(
                "Add products or log sales to enable the Master Excel download."
            )

        st.markdown("---")
        st.subheader("Current Stock & Product Pricing")
        if not products_df.empty:
            products_display = products_df.rename(
                columns={
                    "id": "ID",
                    "name": "Product Name",
                    "sku": "SKU",
                    "landed_cost": "Landed Cost w/ Packaging ($)",
                    "default_price": "Set Selling Price ($)",
                    "stock": "In Stock",
                }
            )
            st.dataframe(products_display, use_container_width=True)
        else:
            st.info(
                "No products added yet. Head to 'Manage Inventory' to start!"
            )

    # -------------------------------------------------------------------
    # TAB 2: MANAGE INVENTORY & INVENTORY EXPORT
    # -------------------------------------------------------------------
    with tabs[1]:
        st.header("Add New Product to NawatCore Inventory")
        with st.form("add_product_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            p_name = col_a.text_input("Product Name")
            p_sku = col_b.text_input("SKU / Item Code")
            p_landed_cost = col_a.number_input(
                "Landed Cost w/ Packaging ($)",
                min_value=0.0,
                step=0.50,
                help="Total cost per unit including item cost + packaging materials.",
            )
            p_default_price = col_b.number_input(
                "Default Set Selling Price ($)", min_value=0.0, step=0.50
            )
            p_stock = col_a.number_input("Initial Stock", min_value=0, step=1)

            submit = st.form_submit_button("Add Product")
            if submit:
                if p_name.strip():
                    try:
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute(
                            "INSERT INTO products (name, sku, landed_cost, default_price, stock) VALUES (?, ?, ?, ?, ?)",
                            (
                                p_name,
                                p_sku,
                                p_landed_cost,
                                p_default_price,
                                p_stock,
                            ),
                        )
                        conn.commit()
                        conn.close()
                        st.success(f"Added **{p_name}** to NawatCore inventory!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("A product with this name already exists.")
                else:
                    st.warning("Please enter a valid product name.")

        # Inventory Export Section
        conn = get_connection()
        inv_df = pd.read_sql_query("SELECT * FROM products", conn)
        conn.close()

        if not inv_df.empty:
            st.markdown("---")
            st.subheader("📥 Export Inventory")
            inv_excel = generate_excel_bytes({"Inventory": inv_df})
            st.download_button(
                label="📦 Download NawatCore Inventory Excel (.xlsx)",
                data=inv_excel,
                file_name=f"NawatCore_Inventory_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # -------------------------------------------------------------------
    # TAB 3: LOG SALES
    # -------------------------------------------------------------------
    with tabs[2]:
        st.header("Record a NawatCore Transaction")
        conn = get_connection()
        products_df = pd.read_sql_query("SELECT * FROM products", conn)
        conn.close()

        if not products_df.empty:
            product_options = {
                f"{row['name']} (Stock: {row['stock']} | Landed Cost: ${row['landed_cost']:.2f} | Set Price: ${row['default_price']:.2f})": row
                for _, row in products_df.iterrows()
            }
            selected_option = st.selectbox(
                "Select Item", list(product_options.keys())
            )
            item = product_options[selected_option]

            col1, col2 = st.columns(2)

            with col1:
                sale_qty = st.number_input(
                    "Quantity Sold",
                    min_value=1,
                    max_value=int(item["stock"]) if item["stock"] > 0 else 1,
                    step=1,
                )

                actual_unit_price = st.number_input(
                    "Actual Sale Price per Unit ($)",
                    min_value=0.0,
                    value=float(item["default_price"]),
                    step=0.50,
                    help="Pre-filled with set price. Change this if sold at a discount or cheaper rate.",
                )

                sale_type = st.radio(
                    "Sale Channel", ["Local", "Online"], horizontal=True
                )

                shipping_cost = 0.0
                if sale_type == "Online":
                    shipping_cost = st.number_input(
                        "Shipping Paid by You ($)",
                        min_value=0.0,
                        value=0.0,
                        step=0.50,
                        help="Amount paid out-of-pocket for shipping to be deducted from sales.",
                    )

            with col2:
                payment_method = st.selectbox(
                    "Payment Method",
                    ["Cash", "Zelle", "Venmo", "Apple Pay", "Cash App", "Other"],
                )

                transaction_date = st.date_input(
                    "Transaction Date", datetime.now()
                )
                transaction_time = st.time_input(
                    "Transaction Time", datetime.now().time()
                )
                sale_timestamp = datetime.combine(
                    transaction_date, transaction_time
                ).strftime("%Y-%m-%d %H:%M:%S")

            gross_total = sale_qty * actual_unit_price
            net_total = gross_total - shipping_cost
            total_landed_cost = sale_qty * item["landed_cost"]
            net_profit = net_total - total_landed_cost

            st.markdown("---")
            st.subheader("Transaction Summary Breakdown")
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("Gross Revenue", f"${gross_total:,.2f}")
            sc2.metric("Shipping Deducted", f"-${shipping_cost:,.2f}")
            sc3.metric("Net Sales", f"${net_total:,.2f}")
            sc4.metric("Estimated Net Profit", f"${net_profit:,.2f}")

            if item["stock"] <= 0:
                st.error("This item is currently out of stock.")
            else:
                if st.button("Complete Sale", type="primary"):
                    conn = get_connection()
                    c = conn.cursor()

                    c.execute(
                        "UPDATE products SET stock = stock - ? WHERE id = ?",
                        (sale_qty, item["id"]),
                    )

                    c.execute(
                        """
                        INSERT INTO sales 
                        (product_id, quantity, unit_sale_price, gross_total, sale_type, shipping_cost, net_total, landed_cost_total, net_profit, payment_method, sale_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            item["id"],
                            sale_qty,
                            actual_unit_price,
                            gross_total,
                            sale_type,
                            shipping_cost,
                            net_total,
                            total_landed_cost,
                            net_profit,
                            payment_method,
                            sale_timestamp,
                        ),
                    )

                    conn.commit()
                    conn.close()

                    st.success("Sale logged successfully!")
                    st.rerun()
        else:
            st.info("Add products to inventory before logging sales.")

    # -------------------------------------------------------------------
    # TAB 4: SALES HISTORY & SALES EXPORT
    # -------------------------------------------------------------------
    with tabs[3]:
        st.header("NawatCore Sales History & Ledger")
        conn = get_connection()
        sales_ledger_df = pd.read_sql_query(
            """
            SELECT s.id AS 'Sale ID', s.sale_date AS 'Date & Time', p.name AS 'Product', 
                   s.quantity AS 'Qty', s.unit_sale_price AS 'Sold Price/Unit', 
                   s.gross_total AS 'Gross Rev', s.sale_type AS 'Type', 
                   s.shipping_cost AS 'Shipping Cost', s.net_total AS 'Net Revenue',
                   s.net_profit AS 'Net Profit', s.payment_method AS 'Payment Method'
            FROM sales s 
            JOIN products p ON s.product_id = p.id
            ORDER BY s.sale_date DESC
        """,
            conn,
        )
        conn.close()

        if not sales_ledger_df.empty:
            st.dataframe(sales_ledger_df, use_container_width=True)

            st.markdown("---")
            st.subheader("📥 Export Sales Ledger")
            sales_excel = generate_excel_bytes({"Sales Ledger": sales_ledger_df})
            st.download_button(
                label="🛒 Download NawatCore Sales Ledger Excel (.xlsx)",
                data=sales_excel,
                file_name=f"NawatCore_Sales_Ledger_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("No sales recorded yet.")