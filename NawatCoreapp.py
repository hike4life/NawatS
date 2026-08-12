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

# --- SQLITE LOCAL DATABASE SETUP ---
DB_FILE = "nawatcore.db"

def init_sqlite_db():
    """Initializes local SQLite database tables if they do not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        sku TEXT,
        category TEXT,
        landed_cost REAL DEFAULT 0.0,
        default_price REAL DEFAULT 0.0,
        stock INTEGER DEFAULT 0
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity INTEGER,
        unit_sale_price REAL,
        gross_total REAL,
        sale_type TEXT,
        shipping_cost REAL,
        net_total REAL,
        landed_cost_total REAL,
        net_profit REAL,
        payment_method TEXT,
        sale_date TEXT,
        notes TEXT,
        FOREIGN KEY (product_id) REFERENCES inventory (id)
    )
    """)
    conn.commit()
    conn.close()

init_sqlite_db()

# --- DATABASE HELPERS ---
def get_db_connection():
    return sqlite3.connect(DB_FILE)

def load_products_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM inventory", conn)
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=["id", "name", "sku", "category", "landed_cost", "default_price", "stock"])
    return df

def load_sales_df():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM sales", conn)
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=[
            "id", "product_id", "quantity", "unit_sale_price", "gross_total", 
            "sale_type", "shipping_cost", "net_total", "landed_cost_total", 
            "net_profit", "payment_method", "sale_date", "notes"
        ])
    return df

def import_excel_to_sqlite(file):
    """Imports Excel sheets (Inventory & Sales) directly into SQLite database."""
    xls = pd.ExcelFile(file)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Import Inventory Sheet
    for sheet in xls.sheet_names:
        if sheet.lower() == "inventory":
            df_inv = pd.read_excel(file, sheet_name=sheet)
            cursor.execute("DELETE FROM inventory")
            conn.commit()
            df_inv.to_sql("inventory", conn, if_exists="append", index=False)
            
        elif sheet.lower() == "sales":
            df_sales = pd.read_excel(file, sheet_name=sheet)
            cursor.execute("DELETE FROM sales")
            conn.commit()
            df_sales.to_sql("sales", conn, if_exists="append", index=False)
            
    conn.close()

# --- VISUAL COLOR THEME ENGINE ---
def get_product_theme(product_name):
    n = str(product_name).lower()
    if any(w in n for w in ["rosewood", "walnut", "wood", "brown", "oak", "mahogany"]):
        return "🪵", "#8B4513", "#FDF6E2", "#4A2306"
    elif any(w in n for w in ["black", "dark", "matte", "obsidian", "night"]):
        return "⚫", "#333333", "#F2F2F2", "#111111"
    elif any(w in n for w in ["silver", "steel", "stainless", "chrome", "grey", "gray", "metal"]):
        return "⚙️", "#718096", "#EDF2F7", "#1A202C"
    elif any(w in n for w in ["white", "cream", "ivory"]):
        return "⚪", "#CBD5E0", "#F7FAFC", "#2D3748"
    elif any(w in n for w in ["duster", "air", "blower"]):
        return "💨", "#319795", "#E6FFFA", "#234E52"
    else:
        return "📦", "#4A5568", "#F7FAFC", "#1A202C"

def render_product_card(row, subtitle="Product Overview"):
    icon, border_col, bg_col, text_col = get_product_theme(row['name'])
    cat = row.get('category', 'General')
    price = float(row.get('default_price', 0.0))
    stock = int(row.get('stock', 0))
    landed = float(row.get('landed_cost', 0.0))
    sku = row.get('sku', 'N/A')
    
    card_html = f"""
    <div style="border-left: 6px solid {border_col}; background-color: {bg_col}; color: {text_col}; padding: 14px 18px; border-radius: 8px; margin-top: 10px; margin-bottom: 18px;">
        <div style="font-size: 0.85em; font-weight: bold; text-transform: uppercase; opacity: 0.75;">{subtitle}</div>
        <div style="font-size: 1.15em; font-weight: bold;">{icon} {row['name']} <span style="font-size: 0.85em; font-weight: normal;">({cat} | SKU: {sku})</span></div>
        <div style="font-size: 0.95em; display: flex; gap: 24px; flex-wrap: wrap; margin-top: 4px;">
            <span>📦 <b>In Stock:</b> {stock} units</span>
            <span>🏷️ <b>Set Price:</b> ${price:.2f}</span>
            <span>💵 <b>Landed Cost:</b> ${landed:.2f}</span>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

# --- EXCEL GENERATOR ---
def generate_excel_bytes():
    inv_df = load_products_df()
    sales_df = load_sales_df()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        inv_df.to_excel(writer, sheet_name="Inventory", index=False)
        sales_df.to_excel(writer, sheet_name="Sales", index=False)
    return output.getvalue()

# --- AUTHENTICATION ---
def secrets_to_dict(obj):
    if hasattr(obj, "items"):
        return {k: secrets_to_dict(v) for k, v in obj.items()}
    return obj

try:
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

st.title("🏢 NawatCore")
st.caption("Official Inventory & Sales Management Portal")
st.markdown("---")

authenticator.login()

if st.session_state.get("authentication_status") is False:
    st.error("Username or password is incorrect.")
elif st.session_state.get("authentication_status") is None:
    st.warning("Please enter your credentials to log in to NawatCore.")
elif st.session_state.get("authentication_status"):

    st.sidebar.title("🏢 NawatCore")
    st.sidebar.caption("Management Console")
    st.sidebar.write(f"Logged in as: **{st.session_state['name']}**")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📤 Import Data from Excel")
    uploaded_excel = st.sidebar.file_uploader("Upload Excel File (.xlsx)", type=["xlsx"])
    if uploaded_excel is not None:
        if st.sidebar.button("📥 Import & Replace Database", type="primary"):
            try:
                import_excel_to_sqlite(uploaded_excel)
                st.sidebar.success("Database successfully updated from Excel file!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error importing file: {e}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("💾 Export Backup")
    excel_data_side = generate_excel_bytes()
    st.sidebar.download_button(
        label="Download Backup (.xlsx)",
        data=excel_data_side,
        file_name=f"NawatCore_Backup_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    authenticator.logout("Log Out", "sidebar")

    st.title("📦 NawatCore | Inventory & Sales Management Hub")

    tabs = st.tabs([
        "📊 Dashboard",
        "➕ Manage Inventory & Edit Items",
        "🛒 Log Sales",
        "📜 Sales History & Edit Transactions",
    ])

    # -------------------------------------------------------------------
    # TAB 1: DASHBOARD
    # -------------------------------------------------------------------
    with tabs[0]:
        st.header("NawatCore Business Overview")
        products_df = load_products_df()
        sales_raw_df = load_sales_df()

        if not products_df.empty:
            if not sales_raw_df.empty and "product_id" in sales_raw_df.columns:
                prod_stats = sales_raw_df.groupby("product_id").agg(
                    Total_Units_Sold=("quantity", "sum"),
                    Total_Net_Profit=("net_profit", "sum")
                ).reset_index()

                units_sold_df = products_df.merge(prod_stats, left_on="id", right_on="product_id", how="left").fillna(0)
                units_sold_df["Total Units Sold"] = units_sold_df["Total_Units_Sold"].astype(int)
                units_sold_df["Total Net Profit"] = units_sold_df["Total_Net_Profit"].apply(lambda x: f"${x:,.2f}")
            else:
                units_sold_df = products_df.copy()
                units_sold_df["Total Units Sold"] = 0
                units_sold_df["Total Net Profit"] = "$0.00"
            
            units_sold_df["Product Name"] = units_sold_df["name"].apply(
                lambda name: f"{get_product_theme(name)[0]} {name}"
            )

            units_display = units_sold_df[["id", "Product Name", "sku", "category", "stock", "Total Units Sold", "Total Net Profit"]].rename(
                columns={"id": "ID", "sku": "SKU", "category": "Category", "stock": "In Stock", "Total Net Profit": "Total Net Profit ($)"}
            )
        else:
            units_display = pd.DataFrame()

        m1, m2, m3, m4 = st.columns(4)
        total_products = len(products_df)
        gross_rev = sales_raw_df["gross_total"].sum() if not sales_raw_df.empty else 0.0
        net_profit = sales_raw_df["net_profit"].sum() if not sales_raw_df.empty else 0.0
        total_units_sold_all = units_display["Total Units Sold"].sum() if not units_display.empty else 0

        m1.metric("Total Products", total_products)
        m2.metric("Gross Revenue", f"${gross_rev:,.2f}")
        m3.metric("Net Profit", f"${net_profit:,.2f}")
        m4.metric("Total Units Sold", f"{total_units_sold_all:,} Units")

        st.markdown("---")
        st.subheader("📊 Product Sales Performance & Stock")
        if not units_display.empty:
            st.dataframe(units_display, width="stretch")
        else:
            st.info("No products in database.")

    # -------------------------------------------------------------------
    # TAB 2: MANAGE INVENTORY, EDIT & RESTOCK
    # -------------------------------------------------------------------
    with tabs[1]:
        st.header("Inventory Management")
        inv_df = load_products_df()

        if not inv_df.empty:
            st.subheader("✏️ Edit Product Details")
            edit_item_options = {
                f"{get_product_theme(row['name'])[0]} {row['name']} (Stock: {row['stock']} | Price: ${row['default_price']:.2f})": row
                for _, row in inv_df.iterrows()
            }
            selected_edit_label = st.selectbox("Select Item to Update", list(edit_item_options.keys()))
            p_edit = edit_item_options[selected_edit_label]

            render_product_card(p_edit, subtitle="Selected Item for Edit")

            with st.form("edit_product_form"):
                ec1, ec2 = st.columns(2)
                ep_name = ec1.text_input("Product Name", value=str(p_edit["name"]))
                ep_sku = ec2.text_input("SKU / Item Code", value=str(p_edit["sku"]))
                ep_category = ec1.text_input("Category", value=str(p_edit["category"]))
                ep_landed_cost = ec2.number_input("Landed Cost ($)", min_value=0.0, value=float(p_edit["landed_cost"]), step=0.50)
                ep_default_price = ec1.number_input("Selling Price ($)", min_value=0.0, value=float(p_edit["default_price"]), step=0.50)
                ep_stock = ec2.number_input("Stock Count", min_value=-9999, value=int(p_edit["stock"]), step=1)

                btn_save_prod = st.form_submit_button("💾 Save Product Details", type="primary")
                if btn_save_prod:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE inventory SET name=?, sku=?, category=?, landed_cost=?, default_price=?, stock=? WHERE id=?
                    """, (ep_name.strip(), ep_sku.strip(), ep_category.strip(), ep_landed_cost, ep_default_price, ep_stock, int(p_edit["id"])))
                    conn.commit()
                    conn.close()
                    st.toast(f"Saved {ep_name}!", icon="✏️")
                    st.rerun()

        st.markdown("---")
        st.subheader("➕ Add Brand New Product")
        with st.form("add_product_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            p_name = col_a.text_input("Product Name")
            p_sku = col_b.text_input("SKU / Item Code")
            p_cat = col_a.text_input("Category", value="General Accessories")
            p_landed_cost = col_b.number_input("Landed Cost ($)", min_value=0.0, step=0.50)
            p_default_price = col_a.number_input("Selling Price ($)", min_value=0.0, step=0.50)
            p_stock = col_b.number_input("Initial Stock", min_value=0, step=1)

            submit = st.form_submit_button("Add New Product")
            if submit and p_name.strip():
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO inventory (name, sku, category, landed_cost, default_price, stock) VALUES (?, ?, ?, ?, ?, ?)
                    """, (p_name.strip(), p_sku.strip(), p_cat.strip(), p_landed_cost, p_default_price, p_stock))
                    conn.commit()
                    conn.close()
                    st.toast(f"Added {p_name} to database!", icon="🎉")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error adding product: {e}")

    # -------------------------------------------------------------------
    # TAB 3: LOG SALES
    # -------------------------------------------------------------------
    with tabs[2]:
        st.header("Record a NawatCore Transaction")
        products_df = load_products_df()

        if not products_df.empty:
            product_options = {
                f"{get_product_theme(row['name'])[0]} [{row['category']}] {row['name']} (Stock: {row['stock']} | ${row['default_price']:.2f})": row
                for _, row in products_df.iterrows()
            }
            selected_option = st.selectbox("Select Item to Sell", list(product_options.keys()))
            item = product_options[selected_option]

            render_product_card(item, subtitle="Selected Sale Details")

            col1, col2 = st.columns(2)
            sale_qty = col1.number_input("Quantity Sold", min_value=1, max_value=int(item["stock"]) if item["stock"] > 0 else 1, step=1)
            actual_unit_price = col1.number_input("Sale Price per Unit ($)", min_value=0.0, value=float(item["default_price"]), step=0.50)
            sale_type = col1.radio("Sale Channel", ["Local", "Online"], horizontal=True)
            shipping_cost = col1.number_input("Shipping Paid ($)", min_value=0.0, value=0.0, step=0.50) if sale_type == "Online" else 0.0

            payment_method = col2.selectbox("Payment Method", ["Cash", "Zelle", "Venmo", "Apple Pay", "Cash App", "Other"])
            transaction_date = col2.date_input("Transaction Date", datetime.now())
            sale_timestamp = transaction_date.strftime("%Y-%m-%d %H:%M:%S")

            sale_notes = st.text_input("Order Notes (Optional)", placeholder="Customer name, pickup info, etc.")

            gross_total = sale_qty * actual_unit_price
            net_total = gross_total - shipping_cost
            total_landed_cost = sale_qty * float(item["landed_cost"])
            net_profit = net_total - total_landed_cost

            if st.button("Complete Sale", type="primary"):
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sales (product_id, quantity, unit_sale_price, gross_total, sale_type, shipping_cost, net_total, landed_cost_total, net_profit, payment_method, sale_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (int(item["id"]), sale_qty, actual_unit_price, gross_total, sale_type, shipping_cost, net_total, total_landed_cost, net_profit, payment_method, sale_timestamp, sale_notes.strip()))
                
                cursor.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (sale_qty, int(item["id"])))
                conn.commit()
                conn.close()

                st.toast("Sale logged permanently!", icon="🛒")
                st.rerun()

    # -------------------------------------------------------------------
    # TAB 4: SALES HISTORY LEDGER
    # -------------------------------------------------------------------
    with tabs[3]:
        st.header("NawatCore Sales Ledger")
        sales_raw_df = load_sales_df()
        products_df = load_products_df()

        if not sales_raw_df.empty and not products_df.empty:
            sales_merged = sales_raw_df.merge(
                products_df[["id", "name"]], left_on="product_id", right_on="id", how="left"
            ).rename(columns={"name": "Product Name"})
            
            sales_merged["Product Name"] = sales_merged["Product Name"].apply(
                lambda name: f"{get_product_theme(name)[0]} {name}"
            )
            st.dataframe(sales_merged, width="stretch")
        else:
            st.info("No sales recorded yet.")