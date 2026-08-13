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

# --- MOBILE ADAPTABILITY & RESPONSIVE CSS INJECTION ---
st.markdown("""
<style>
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 1rem !important;
            padding-bottom: 2rem !important;
        }
        .stButton > button, div[data-baseweb="select"] {
            width: 100% !important;
        }
        div[data-testid="stMetric"] {
            background-color: rgba(128, 128, 128, 0.08) !important;
            border: 1px solid rgba(128, 128, 128, 0.2) !important;
            padding: 12px 14px !important;
            border-radius: 8px !important;
            margin-bottom: 8px !important;
        }
        button[data-baseweb="tab"] {
            font-size: 0.8em !important;
            padding: 6px 6px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

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

def execute_quick_sale(product_row, qty=1, payment_method="Cash", channel="Local", notes="Quick Express Log"):
    """Helper to log a fast sale transaction and adjust inventory stock instantly."""
    p_id = int(product_row["id"])
    unit_price = float(product_row["default_price"])
    landed_unit = float(product_row["landed_cost"])
    
    gross = qty * unit_price
    shipping = 0.0
    net = gross - shipping
    landed_tot = qty * landed_unit
    profit = net - landed_tot
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sales (product_id, quantity, unit_sale_price, gross_total, sale_type, shipping_cost, net_total, landed_cost_total, net_profit, payment_method, sale_date, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (p_id, qty, unit_price, gross, channel, shipping, net, landed_tot, profit, payment_method, now_str, notes))
    
    cursor.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (qty, p_id))
    conn.commit()
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
    <div style="border-left: 6px solid {border_col}; background-color: {bg_col}; color: {text_col}; padding: 12px 16px; border-radius: 8px; margin-top: 10px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
        <div style="font-size: 0.8em; font-weight: bold; text-transform: uppercase; opacity: 0.75; letter-spacing: 0.5px;">{subtitle}</div>
        <div style="font-size: 1.1em; font-weight: bold; margin-top: 2px;">{icon} {row['name']} <span style="font-size: 0.85em; font-weight: normal; opacity: 0.85;">({cat} | SKU: {sku})</span></div>
        <div style="font-size: 0.9em; display: flex; gap: 16px; flex-wrap: wrap; margin-top: 6px;">
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
        if st.sidebar.button("📥 Import & Replace Database", type="primary", use_container_width=True):
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

    st.title("📦 NawatCore | Inventory & Sales Hub")

    tabs = st.tabs([
        "📊 Dashboard",
        "⚡ Express Sale",
        "🛒 Detailed Sale",
        "➕ Manage Inventory",
        "📜 Sales Ledger",
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

        # RECENT SALES SUMMARY
        st.subheader("⚡ Recent Activity (Last 5 Sales)")
        if not sales_raw_df.empty and not products_df.empty:
            recent_sales = sales_raw_df.sort_values(by="id", ascending=False).head(5).copy()
            recent_merged = recent_sales.merge(
                products_df[["id", "name"]], 
                left_on="product_id", 
                right_on="id", 
                how="left", 
                suffixes=("", "_prod")
            ).rename(columns={"name": "Product Name"})

            recent_merged["Product"] = recent_merged["Product Name"].apply(
                lambda name: f"{get_product_theme(name)[0]} {name}" if pd.notna(name) else "📦 General Product"
            )

            recent_merged["Gross Total ($)"] = recent_merged["gross_total"].apply(lambda x: f"${x:,.2f}")
            recent_merged["Net Profit ($)"] = recent_merged["net_profit"].apply(lambda x: f"${x:,.2f}")

            disp_recent = recent_merged[[
                "id", "sale_date", "Product", "quantity", 
                "Gross Total ($)", "Net Profit ($)", "payment_method", "sale_type"
            ]].rename(columns={
                "id": "Sale ID", 
                "sale_date": "Date", 
                "quantity": "Qty", 
                "payment_method": "Payment", 
                "sale_type": "Channel"
            })

            st.dataframe(disp_recent, width="stretch", hide_index=True)
        else:
            st.info("No recent sales logged yet.")

        st.markdown("---")
        st.subheader("📊 Product Sales Performance & Stock")
        if not units_display.empty:
            st.dataframe(units_display, width="stretch")
        else:
            st.info("No products in database.")

    # -------------------------------------------------------------------
    # TAB 2: ⚡ EXPRESS SALE (1-TAP CHECKOUT)
    # -------------------------------------------------------------------
    with tabs[1]:
        st.header("⚡ Express Checkout (1-Tap Fast Log)")
        st.caption("Tap any product button below to instantly record a 1-unit sale at default price!")
        products_df = load_products_df()

        if not products_df.empty:
            # Payment Method Quick Toggle
            quick_pay = st.radio("Payment Method for Express Log", ["Cash", "Venmo", "Zelle", "Apple Pay", "Ebay", "MP"], horizontal=True)
            st.markdown("---")

            st.subheader("🔥 Quick Tap Best Sellers")
            # Filter in-stock items
            in_stock_df = products_df[products_df["stock"] > 0]

            if not in_stock_df.empty:
                cols = st.columns(2)
                for idx, (_, row) in enumerate(in_stock_df.iterrows()):
                    col_target = cols[idx % 2]
                    icon, _, _, _ = get_product_theme(row["name"])
                    btn_label = f"{icon} Sell 1x {row['name']} (${row['default_price']:.2f}) | Stock: {row['stock']}"
                    
                    if col_target.button(btn_label, key=f"quick_btn_{row['id']}", use_container_width=True):
                        execute_quick_sale(row, qty=1, payment_method=quick_pay)
                        st.toast(f"Logged 1x {row['name']} via {quick_pay}!", icon="⚡")
                        st.rerun()
            else:
                st.warning("All inventory items currently show 0 stock.")

            st.markdown("---")
            st.subheader("🚀 Fast Quantity Log")
            with st.form("express_custom_form"):
                ex_item_options = {
                    f"{get_product_theme(r['name'])[0]} {r['name']} (Stock: {r['stock']} | ${r['default_price']:.2f})": r
                    for _, r in products_df.iterrows()
                }
                sel_ex_label = st.selectbox("Select Product", list(ex_item_options.keys()))
                ex_item = ex_item_options[sel_ex_label]

                fc1, fc2 = st.columns(2)
                ex_qty = fc1.number_input("Quantity", min_value=1, max_value=int(ex_item['stock']) if ex_item['stock'] > 0 else 1, value=1, step=1)
                ex_price = fc2.number_input("Unit Price ($)", min_value=0.0, value=float(ex_item['default_price']), step=0.50)

                btn_ex_submit = st.form_submit_button("⚡ Instant Log Sale", type="primary", use_container_width=True)
                if btn_ex_submit:
                    # Update row price if custom price entered
                    ex_item_copy = ex_item.copy()
                    ex_item_copy["default_price"] = ex_price
                    execute_quick_sale(ex_item_copy, qty=ex_qty, payment_method=quick_pay, notes="Express Form Log")
                    st.toast(f"Logged {ex_qty}x {ex_item['name']}!", icon="🚀")
                    st.rerun()

    # -------------------------------------------------------------------
    # TAB 3: DETAILED SALE (FULL CONTROL)
    # -------------------------------------------------------------------
    with tabs[2]:
        st.header("Record Detailed Transaction")
        products_df = load_products_df()

        if not products_df.empty:
            st.subheader("🔍 Narrow Search by Category")
            avail_cats = ["All Categories"] + sorted(list(products_df["category"].dropna().unique()))
            selected_sale_cat = st.selectbox("Filter Product List by Category", avail_cats)

            if selected_sale_cat != "All Categories":
                filtered_sale_prods = products_df[products_df["category"] == selected_sale_cat]
            else:
                filtered_sale_prods = products_df

            if not filtered_sale_prods.empty:
                product_options = {
                    f"{get_product_theme(row['name'])[0]} [{row['category']}] {row['name']} (Stock: {row['stock']} | ${row['default_price']:.2f})": row
                    for _, row in filtered_sale_prods.iterrows()
                }
                selected_option = st.selectbox("Select Item to Sell", list(product_options.keys()))
                item = product_options[selected_option]

                render_product_card(item, subtitle="Selected Sale Details")

                col1, col2 = st.columns(2)
                sale_qty = col1.number_input("Quantity Sold", min_value=1, max_value=int(item["stock"]) if item["stock"] > 0 else 1, step=1)
                actual_unit_price = col1.number_input("Sale Price per Unit ($)", min_value=0.0, value=float(item["default_price"]), step=0.50)
                sale_type = col1.radio("Sale Channel", ["Local", "Online"], horizontal=True)
                shipping_cost = col1.number_input("Shipping Paid ($)", min_value=0.0, value=0.0, step=0.50) if sale_type == "Online" else 0.0

                payment_method = col2.selectbox("Payment Method", ["Cash", "Venmo", "Zelle", "Apple Pay", "Cash App", "Ebay", "MP", "Other"])
                transaction_date = col2.date_input("Transaction Date", datetime.now())
                sale_timestamp = transaction_date.strftime("%Y-%m-%d %H:%M:%S")

                sale_notes = st.text_input("Order Notes (Optional)", placeholder="Customer name, pickup info, etc.")

                gross_total = sale_qty * actual_unit_price
                net_total = gross_total - shipping_cost
                total_landed_cost = sale_qty * float(item["landed_cost"])
                net_profit = net_total - total_landed_cost

                if st.button("Complete Detailed Sale", type="primary", use_container_width=True):
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
    # TAB 4: MANAGE INVENTORY, CATEGORY FILTER & EDIT ITEMS
    # -------------------------------------------------------------------
    with tabs[3]:
        st.header("Inventory Management")
        inv_df = load_products_df()

        if not inv_df.empty:
            st.subheader("🔍 Filter Inventory by Category")
            avail_inv_cats = ["All Categories"] + sorted(list(inv_df["category"].dropna().unique()))
            selected_inv_cat = st.selectbox("Select Category to Filter Products", avail_inv_cats)

            if selected_inv_cat != "All Categories":
                filtered_inv_df = inv_df[inv_df["category"] == selected_inv_cat]
            else:
                filtered_inv_df = inv_df

            st.markdown("---")
            st.subheader("✏️ Edit Product Details & Stock Count")
            if not filtered_inv_df.empty:
                edit_item_options = {
                    f"{get_product_theme(row['name'])[0]} [{row['category']}] {row['name']} (Stock: {row['stock']} | Price: ${row['default_price']:.2f})": row
                    for _, row in filtered_inv_df.iterrows()
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

                    btn_save_prod = st.form_submit_button("💾 Save Product Details", type="primary", use_container_width=True)
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
            else:
                st.warning("No products found in this category.")

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

            submit = st.form_submit_button("Add New Product", use_container_width=True)
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

        if not inv_df.empty:
            st.markdown("---")
            st.subheader("📋 Current Stock Overview")
            display_inv_table = filtered_inv_df.copy()
            display_inv_table["Product Name"] = display_inv_table["name"].apply(
                lambda name: f"{get_product_theme(name)[0]} {name}"
            )
            st.dataframe(
                display_inv_table[["id", "Product Name", "sku", "category", "landed_cost", "default_price", "stock"]].rename(columns={
                    "id": "ID", "sku": "SKU", "category": "Category", "landed_cost": "Landed Cost ($)",
                    "default_price": "Selling Price ($)", "stock": "Current Stock"
                }),
                width="stretch"
            )

    # -------------------------------------------------------------------
    # TAB 5: SALES HISTORY, FILTERS & EDIT TRANSACTIONS
    # -------------------------------------------------------------------
    with tabs[4]:
        st.header("NawatCore Sales Ledger & Order Editing")
        sales_raw_df = load_sales_df()
        products_df = load_products_df()

        if not sales_raw_df.empty and not products_df.empty:
            sales_merged = sales_raw_df.merge(
                products_df[["id", "name", "category", "landed_cost"]], 
                left_on="product_id", 
                right_on="id", 
                how="left", 
                suffixes=("", "_prod")
            ).rename(columns={"name": "Product Name", "category": "Category", "landed_cost": "prod_landed_cost"})
            
            sales_merged["Product Display"] = sales_merged["Product Name"].apply(
                lambda name: f"{get_product_theme(name)[0]} {name}" if pd.notna(name) else "📦 General Product"
            )

            st.subheader("🔍 Filter Sales Ledger")
            fc1, fc2, fc3, fc4 = st.columns(4)

            # Category Filter Dropdown
            all_cats = ["All Categories"] + sorted(list(sales_merged["Category"].dropna().unique()))
            selected_cat = fc1.selectbox("Filter by Category", all_cats)

            # Product Filter Dropdown
            if selected_cat != "All Categories":
                cat_filtered_sales = sales_merged[sales_merged["Category"] == selected_cat]
            else:
                cat_filtered_sales = sales_merged

            all_prods = ["All Products"] + sorted(list(cat_filtered_sales["Product Display"].dropna().unique()))
            selected_prod = fc2.selectbox("Filter by Product", all_prods)

            # Payment Method Filter
            all_pay = ["All Payment Methods"] + sorted(list(sales_merged["payment_method"].dropna().unique()))
            selected_pay = fc3.selectbox("Filter by Payment Method", all_pay)

            # Sale Channel Filter
            selected_channel = fc4.selectbox("Filter by Channel", ["All Channels", "Local", "Online"])

            # Apply All Active Filters
            filtered_ledger = sales_merged.copy()

            if selected_cat != "All Categories":
                filtered_ledger = filtered_ledger[filtered_ledger["Category"] == selected_cat]
            if selected_prod != "All Products":
                filtered_ledger = filtered_ledger[filtered_ledger["Product Display"] == selected_prod]
            if selected_pay != "All Payment Methods":
                filtered_ledger = filtered_ledger[filtered_ledger["payment_method"] == selected_pay]
            if selected_channel != "All Channels":
                filtered_ledger = filtered_ledger[filtered_ledger["sale_type"] == selected_channel]

            # Metric Bar for Filtered Results
            f_rev = filtered_ledger["gross_total"].sum() if not filtered_ledger.empty else 0.0
            f_profit = filtered_ledger["net_profit"].sum() if not filtered_ledger.empty else 0.0
            f_units = filtered_ledger["quantity"].sum() if not filtered_ledger.empty else 0

            st.info(
                f"Showing **{len(filtered_ledger)}** matching sales | **{f_units}** Units Sold | **${f_rev:,.2f}** Revenue | **${f_profit:,.2f}** Profit"
            )

            display_cols = [
                "id", "sale_date", "Category", "Product Display", "quantity", 
                "unit_sale_price", "gross_total", "landed_cost_total", 
                "net_profit", "payment_method", "sale_type", "notes"
            ]
            
            valid_cols = [c for c in display_cols if c in filtered_ledger.columns]

            st.dataframe(
                filtered_ledger[valid_cols].rename(columns={
                    "id": "Sale ID", "sale_date": "Date", "quantity": "Qty",
                    "unit_sale_price": "Price/Unit", "gross_total": "Gross Rev",
                    "landed_cost_total": "Landed Cost", "net_profit": "Net Profit",
                    "payment_method": "Payment", "sale_type": "Channel", "notes": "Notes"
                }),
                width="stretch"
            )

            st.markdown("---")

            # EDIT OR DELETE TRANSACTION SECTION
            st.subheader("✏️ Modify or Delete Existing Sale Record")
            st.caption("The list below automatically filters to show only the matching sales from the table above.")

            if not filtered_ledger.empty:
                sale_list = {
                    f"Sale #{row['id']} - {row['Product Display']} (Qty: {row['quantity']} | ${row['gross_total']:.2f} on {row['sale_date']})": row
                    for _, row in filtered_ledger.iterrows()
                }
                selected_sale_label = st.selectbox("Select Sale Record to Modify or Delete", list(sale_list.keys()))
                s_edit = sale_list[selected_sale_label]

                with st.form("edit_sale_form"):
                    ec1, ec2 = st.columns(2)

                    with ec1:
                        e_qty = ec1.number_input("Quantity Sold", min_value=1, value=int(s_edit["quantity"]), step=1)
                        e_unit_price = ec1.number_input("Sale Price per Unit ($)", min_value=0.0, value=float(s_edit["unit_sale_price"]), step=0.50)
                        e_type = ec1.radio("Sale Channel", ["Local", "Online"], index=0 if s_edit["sale_type"] == "Local" else 1, horizontal=True)
                        
                        e_shipping = 0.0
                        if e_type == "Online":
                            e_shipping = ec1.number_input("Shipping Paid ($)", min_value=0.0, value=float(s_edit["shipping_cost"]), step=0.50)

                    with ec2:
                        pay_options = ["Cash", "Venmo", "Zelle", "Apple Pay", "Cash App", "Ebay", "MP", "Other"]
                        default_pay_idx = pay_options.index(s_edit["payment_method"]) if s_edit["payment_method"] in pay_options else 0
                        e_payment = ec2.selectbox("Payment Method", pay_options, index=default_pay_idx)
                        
                        parsed_dt = pd.to_datetime(s_edit["sale_date"], errors='coerce')
                        if pd.isna(parsed_dt):
                            parsed_dt = datetime.now()

                        e_date = ec2.date_input("Transaction Date", parsed_dt.date())
                        e_timestamp = e_date.strftime("%Y-%m-%d %H:%M:%S")

                    e_notes = st.text_input("Comments / Notes", value=str(s_edit["notes"]) if pd.notna(s_edit["notes"]) else "")

                    e_gross = e_qty * e_unit_price
                    e_net = e_gross - e_shipping
                    item_landed = float(s_edit["prod_landed_cost"]) if pd.notna(s_edit["prod_landed_cost"]) else 0.0
                    e_landed_total = e_qty * item_landed
                    e_profit = e_net - e_landed_total
                    qty_difference = e_qty - int(s_edit["quantity"])

                    btn_col1, btn_col2 = st.columns(2)
                    btn_edit = btn_col1.form_submit_button("💾 Save Updated Sale Record", type="primary", use_container_width=True)
                    btn_delete = btn_col2.form_submit_button("🗑️ Fully Delete Sale Record", type="secondary", use_container_width=True)

                    if btn_edit:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE sales 
                            SET quantity=?, unit_sale_price=?, gross_total=?, sale_type=?, shipping_cost=?, net_total=?, landed_cost_total=?, net_profit=?, payment_method=?, sale_date=?, notes=?
                            WHERE id=?
                        """, (e_qty, e_unit_price, e_gross, e_type, e_shipping, e_net, e_landed_total, e_profit, e_payment, e_timestamp, e_notes.strip(), int(s_edit["id"])))

                        if qty_difference != 0:
                            cursor.execute("UPDATE inventory SET stock = stock - ? WHERE id = ?", (qty_difference, int(s_edit["product_id"])))

                        conn.commit()
                        conn.close()

                        st.toast(f"Updated Sale #{s_edit['id']}!", icon="✏️")
                        st.rerun()

                    if btn_delete:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM sales WHERE id = ?", (int(s_edit["id"]),))
                        cursor.execute("UPDATE inventory SET stock = stock + ? WHERE id = ?", (int(s_edit["quantity"]), int(s_edit["product_id"])))
                        conn.commit()
                        conn.close()

                        st.toast(f"Deleted Sale #{s_edit['id']} and restored {s_edit['quantity']} unit(s) back to inventory!", icon="🗑️")
                        st.rerun()
            else:
                st.warning("No sales match the active filters above.")
        else:
            st.info("No sales recorded yet.")