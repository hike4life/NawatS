from datetime import datetime
import io
import json
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
def secrets_to_dict(obj):
    """Recursively converts Streamlit AttrDict objects into standard Python dicts."""
    if hasattr(obj, "items"):
        return {k: secrets_to_dict(v) for k, v in obj.items()}
    return obj


try:
    # Recursively convert st.secrets into a standard mutable dictionary
    credentials = secrets_to_dict(st.secrets["credentials"])
    stauth.Hasher.hash_passwords(credentials)
except Exception as e:
    st.error(f"⚠️ Secrets configuration error: {e}")
    st.stop()

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

authenticator.login()

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
            "📜 Sales History & Returns",
        ]
    )

    # -------------------------------------------------------------------
    # TAB 1: DASHBOARD
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

        m1, m2, m3, m4 = st.columns(4)
        total_products = len(products_df)
        gross_rev = sales_df["Gross Rev"].sum() if not sales_df.empty else 0.0
        net_profit = sales_df["Net Profit"].sum() if not sales_df.empty else 0.0
        net_margin = (net_profit / gross_rev * 100) if gross_rev > 0 else 0.0
        low_stock = (
            len(products_df[products_df["stock"] < 5])
            if not products_df.empty
            else 0
        )

        m1.metric("Total Products", total_products)
        m2.metric("Gross Revenue", f"${gross_rev:,.2f}")
        m3.metric("Net Profit", f"${net_profit:,.2f}", delta=f"{net_margin:.1f}% Margin")
        m4.metric("Low Stock Items (<5)", low_stock)

        st.markdown("---")

        st.subheader("📥 Export Reports")
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
            st.info("Add products or log sales to enable Master Excel download.")

        st.markdown("---")
        st.subheader("Current Stock & Profitability")
        if not products_df.empty:
            display_df = products_df.copy()
            # Calculate % Markup per item
            display_df["Markup %"] = (
                (display_df["default_price"] - display_df["landed_cost"])
                / display_df["landed_cost"].replace(0, 1)
                * 100
            ).round(1).astype(str) + "%"

            display_df = display_df.rename(
                columns={
                    "id": "ID",
                    "name": "Product Name",
                    "sku": "SKU",
                    "landed_cost": "Landed Cost ($)",
                    "default_price": "Selling Price ($)",
                    "stock": "In Stock",
                }
            )[["ID", "Product Name", "SKU", "Landed Cost ($)", "Selling Price ($)", "Markup %", "In Stock"]]
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("No products added yet. Head to 'Manage Inventory' to start!")

    # -------------------------------------------------------------------
    # TAB 2: MANAGE INVENTORY
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
                    )

            with col2:
                payment_method = st.selectbox(
                    "Payment Method",
                    ["Cash", "Zelle", "Venmo", "Apple Pay", "Cash App", "Other"],
                )

                transaction_date = st.date_input("Transaction Date", datetime.now())
                transaction_time = st.time_input("Transaction Time", datetime.now().time())
                sale_timestamp = datetime.combine(
                    transaction_date, transaction_time
                ).strftime("%Y-%m-%d %H:%M:%S")

            gross_total = sale_qty * actual_unit_price
            net_total = gross_total - shipping_cost
            total_landed_cost = sale_qty * item["landed_cost"]
            net_profit = net_total - total_landed_cost
            item_profit_margin = (net_profit / gross_total * 100) if gross_total > 0 else 0.0

            st.markdown("---")
            st.subheader("Transaction Summary Breakdown")
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("Gross Revenue", f"${gross_total:,.2f}")
            sc2.metric("Shipping Deducted", f"-${shipping_cost:,.2f}")
            sc3.metric("Net Sales", f"${net_total:,.2f}")
            sc4.metric("Net Profit", f"${net_profit:,.2f}", delta=f"{item_profit_margin:.1f}% Margin")

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
    # TAB 4: SALES HISTORY, RETURNS & VOIDING SALES
    # -------------------------------------------------------------------
    with tabs[3]:
        st.header("NawatCore Sales Ledger & Order Management")
        conn = get_connection()
        sales_raw = pd.read_sql_query(
            """
            SELECT s.id AS 'Sale ID', s.sale_date AS 'Date & Time', p.name AS 'Product', s.product_id,
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

        if not sales_raw.empty:
            # Add Profit Margin % Column
            display_ledger = sales_raw.copy()
            display_ledger["Margin %"] = (
                (display_ledger["Net Profit"] / display_ledger["Gross Rev"].replace(0, 1)) * 100
            ).round(1).astype(str) + "%"

            cols_to_show = [
                'Sale ID', 'Date & Time', 'Product', 'Qty', 'Sold Price/Unit',
                'Gross Rev', 'Shipping Cost', 'Net Revenue', 'Net Profit', 'Margin %', 'Payment Method', 'Type'
            ]
            st.dataframe(display_ledger[cols_to_show], use_container_width=True)

            st.markdown("---")

            # VOID / RETURN SALE SECTION
            st.subheader("🔄 Void Transaction / Process Return")
            st.caption("Remove a sale entered by mistake or process a customer return.")

            col_void1, col_void2 = st.columns(2)
            with col_void1:
                sale_list = {
                    f"ID #{row['Sale ID']} - {row['Product']} (Qty: {row['Qty']} | ${row['Gross Rev']:.2f} on {row['Date & Time']})": row
                    for _, row in sales_raw.iterrows()
                }
                selected_sale_label = st.selectbox("Select Sale to Cancel / Void", list(sale_list.keys()))
                selected_sale = sale_list[selected_sale_label]

            with col_void2:
                return_to_stock = st.radio(
                    "Action Type:",
                    ["Return item(s) to inventory (Customer Return / Accidental Entry)", "Do NOT return to inventory (Damaged Goods / Loss / Write-off)"]
                )

                if st.button("❌ Cancel / Void This Sale", type="primary"):
                    conn = get_connection()
                    c = conn.cursor()

                    # Step 1: Restore stock if requested
                    if "Return item(s) to inventory" in return_to_stock:
                        c.execute(
                            "UPDATE products SET stock = stock + ? WHERE id = ?",
                            (selected_sale["Qty"], selected_sale["product_id"])
                        )

                    # Step 2: Delete transaction from database
                    c.execute("DELETE FROM sales WHERE id = ?", (selected_sale["Sale ID"],))
                    conn.commit()
                    conn.close()

                    st.success(f"Successfully voided Sale #{selected_sale['Sale ID']}!")
                    st.rerun()

            st.markdown("---")
            st.subheader("📥 Export Sales Ledger")
            sales_excel = generate_excel_bytes({"Sales Ledger": display_ledger[cols_to_show]})
            st.download_button(
                label="🛒 Download NawatCore Sales Ledger Excel (.xlsx)",
                data=sales_excel,
                file_name=f"NawatCore_Sales_Ledger_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.info("No sales recorded yet.")