from datetime import datetime
import io
import requests
import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth

# --- STREAMLIT PAGE CONFIG ---
st.set_page_config(
    page_title="NawatCore - Inventory & Sales Hub",
    layout="wide",
    page_icon="🏢",
)

# --- GOOGLE SHEETS WEBHOOK API HELPERS ---
API_URL = st.secrets.get("SHEET_API_URL", "")

DEFAULT_CATEGORIES = [
    "Portafilters - 58mm",
    "Portafilters - 54mm",
    "Portafilters - 51mm / Other",
    "Coffee Grinders",
    "Coffee Filters & Screens",
    "Electronic Utility Dusters",
    "General Accessories",
]

def fetch_sheet_data(action):
    """Fetches data directly from Google Apps Script Webhook."""
    if not API_URL:
        st.error("⚠️ SHEET_API_URL missing from Streamlit Secrets!")
        return pd.DataFrame()
    try:
        res = requests.get(f"{API_URL}?action={action}", timeout=10)
        data = res.json()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            return df
        return pd.DataFrame(columns=data[0] if data else [])
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return pd.DataFrame()

# --- CACHED DATA LOADERS WITH SESSION STATE ---
def load_products_df(force_reload=False):
    if "products_df" not in st.session_state or force_reload:
        df = fetch_sheet_data("getInventory")
        if df.empty or "id" not in df.columns:
            st.session_state["products_df"] = pd.DataFrame(columns=["id", "name", "sku", "category", "landed_cost", "default_price", "stock"])
        else:
            if "category" not in df.columns:
                df["category"] = "General Accessories"
            df["category"] = df["category"].fillna("General Accessories").astype(str)
            df["id"] = pd.to_numeric(df["id"], errors='coerce').fillna(0).astype(int)
            df["landed_cost"] = pd.to_numeric(df["landed_cost"], errors='coerce').fillna(0.0)
            df["default_price"] = pd.to_numeric(df["default_price"], errors='coerce').fillna(0.0)
            df["stock"] = pd.to_numeric(df["stock"], errors='coerce').fillna(0).astype(int)
            st.session_state["products_df"] = df
    return st.session_state["products_df"]

def load_sales_df(force_reload=False):
    if "sales_df" not in st.session_state or force_reload:
        df = fetch_sheet_data("getSales")
        if df.empty or "id" not in df.columns:
            st.session_state["sales_df"] = pd.DataFrame(columns=[
                "id", "product_id", "quantity", "unit_sale_price", "gross_total", 
                "sale_type", "shipping_cost", "net_total", "landed_cost_total", 
                "net_profit", "payment_method", "sale_date", "notes"
            ])
        else:
            df["id"] = pd.to_numeric(df["id"], errors='coerce').fillna(0).astype(int)
            df["product_id"] = pd.to_numeric(df["product_id"], errors='coerce').fillna(0).astype(int)
            df["quantity"] = pd.to_numeric(df["quantity"], errors='coerce').fillna(0).astype(int)
            df["unit_sale_price"] = pd.to_numeric(df["unit_sale_price"], errors='coerce').fillna(0.0)
            df["gross_total"] = pd.to_numeric(df["gross_total"], errors='coerce').fillna(0.0)
            df["shipping_cost"] = pd.to_numeric(df["shipping_cost"], errors='coerce').fillna(0.0)
            df["net_total"] = pd.to_numeric(df["net_total"], errors='coerce').fillna(0.0)
            df["landed_cost_total"] = pd.to_numeric(df["landed_cost_total"], errors='coerce').fillna(0.0)
            df["net_profit"] = pd.to_numeric(df["net_profit"], errors='coerce').fillna(0.0)
            st.session_state["sales_df"] = df
    return st.session_state["sales_df"]

def send_to_google_sheet(payload):
    """Sends payload asynchronously to Google Sheets Webhook."""
    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False

# --- EXCEL GENERATOR HELPER ---
def generate_excel_bytes(dataframes_dict):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dataframes_dict.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()

# --- USER AUTHENTICATION ---
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
    
    if st.sidebar.button("🔄 Sync with Google Sheets"):
        load_products_df(force_reload=True)
        load_sales_df(force_reload=True)
        st.toast("Refreshed live data from Google Sheets!", icon="🔄")
        st.rerun()

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
                units_sold = sales_raw_df.groupby("product_id")["quantity"].sum().reset_index()
                units_sold_df = products_df.merge(units_sold, left_on="id", right_on="product_id", how="left").fillna(0)
                units_sold_df["Total Units Sold"] = units_sold_df["quantity"].astype(int)
            else:
                units_sold_df = products_df.copy()
                units_sold_df["Total Units Sold"] = 0
            
            units_display = units_sold_df[["id", "name", "sku", "category", "stock", "Total Units Sold"]].rename(
                columns={"id": "ID", "name": "Product Name", "sku": "SKU", "category": "Category", "stock": "In Stock"}
            )
        else:
            units_display = pd.DataFrame()

        m1, m2, m3, m4 = st.columns(4)
        total_products = len(products_df)
        gross_rev = sales_raw_df["gross_total"].sum() if not sales_raw_df.empty and "gross_total" in sales_raw_df.columns else 0.0
        net_profit = sales_raw_df["net_profit"].sum() if not sales_raw_df.empty and "net_profit" in sales_raw_df.columns else 0.0
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
            st.info("No products found in Google Sheets.")

        st.markdown("---")
        st.subheader("📥 Export Reports")
        if not products_df.empty or not sales_raw_df.empty:
            excel_data = generate_excel_bytes({
                "Inventory": products_df, 
                "Sales Ledger": sales_raw_df, 
                "Units Sold Summary": units_display
            })
            st.download_button(
                label="📊 Download Complete NawatCore Excel Report (.xlsx)",
                data=excel_data,
                file_name=f"NawatCore_Full_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )

    # -------------------------------------------------------------------
    # TAB 2: MANAGE INVENTORY, EDIT & RESTOCK
    # -------------------------------------------------------------------
    with tabs[1]:
        st.header("Inventory Management")
        inv_df = load_products_df()

        # Build master category options
        existing_cats = sorted(list(set(inv_df["category"].dropna().unique().tolist() + DEFAULT_CATEGORIES)))

        # SECTION A: EDIT EXISTING INVENTORY ITEM DETAILS / FIX PRICE
        if not inv_df.empty:
            st.subheader("✏️ Edit Product Details (Fix Price, Name, Category, or SKU)")
            edit_item_options = {
                f"{row['name']} (Category: {row['category']} | Price: ${row['default_price']:.2f} | Stock: {row['stock']})": row
                for _, row in inv_df.iterrows()
            }
            selected_edit_label = st.selectbox("Select Item to Update", list(edit_item_options.keys()))
            p_edit = edit_item_options[selected_edit_label]

            with st.form("edit_product_form"):
                ec1, ec2 = st.columns(2)
                ep_name = ec1.text_input("Product Name", value=str(p_edit["name"]))
                ep_sku = ec2.text_input("SKU / Item Code", value=str(p_edit["sku"]))

                current_cat = str(p_edit["category"])
                cat_idx = existing_cats.index(current_cat) if current_cat in existing_cats else 0
                
                ep_cat_select = ec1.selectbox("Category (Select Existing)", existing_cats, index=cat_idx)
                ep_custom_cat = ec2.text_input("Or Type New Category (Optional)", value="", placeholder="e.g. Dosing Cups & Funnels")

                ep_landed_cost = ec1.number_input("Landed Cost w/ Packaging ($)", min_value=0.0, value=float(p_edit["landed_cost"]), step=0.50)
                ep_default_price = ec2.number_input("Default Set Selling Price ($)", min_value=0.0, value=float(p_edit["default_price"]), step=0.50)
                ep_stock = ec1.number_input("Current Stock Count", min_value=-9999, value=int(p_edit["stock"]), step=1)

                btn_save_prod = st.form_submit_button("💾 Save Product Details", type="primary")
                if btn_save_prod:
                    final_cat = ep_custom_cat.strip() if ep_custom_cat.strip() else ep_cat_select
                    
                    # Update memory instantly
                    idx = st.session_state["products_df"].index[st.session_state["products_df"]["id"] == int(p_edit["id"])].tolist()
                    if idx:
                        st.session_state["products_df"].loc[idx[0]] = [
                            int(p_edit["id"]), ep_name.strip(), ep_sku.strip(),
                            final_cat, ep_landed_cost, ep_default_price, ep_stock
                        ]

                    # Sync to Google Sheets
                    payload = {
                        "action": "editProduct",
                        "product_id": int(p_edit["id"]),
                        "row": [int(p_edit["id"]), ep_name.strip(), ep_sku.strip(), final_cat, ep_landed_cost, ep_default_price, ep_stock]
                    }
                    send_to_google_sheet(payload)

                    st.toast(f"Updated **{ep_name}** successfully!", icon="✏️")
                    st.rerun()

            st.markdown("---")

            # SECTION B: RESTOCK
            st.subheader("🔄 Restock Existing Inventory Item")
            with st.form("restock_product_form", clear_on_submit=True):
                restock_options = {
                    f"{row['name']} (Current Stock: {row['stock']} | SKU: {row['sku']})": row
                    for _, row in inv_df.iterrows()
                }
                selected_restock_label = st.selectbox("Select Product to Restock", list(restock_options.keys()))
                restock_item = restock_options[selected_restock_label]
                
                added_stock = st.number_input("Units Received / Added", min_value=1, step=1, value=10)
                
                restock_submit = st.form_submit_button("📥 Add Stock to Inventory", type="primary")
                if restock_submit:
                    idx = st.session_state["products_df"].index[st.session_state["products_df"]["id"] == int(restock_item["id"])].tolist()
                    if idx:
                        st.session_state["products_df"].at[idx[0], "stock"] += int(added_stock)

                    payload = {
                        "action": "restockProduct",
                        "product_id": int(restock_item["id"]),
                        "added_qty": int(added_stock)
                    }
                    send_to_google_sheet(payload)

                    st.toast(f"Added +{added_stock} units to {restock_item['name']}!", icon="✅")
                    st.rerun()

            st.markdown("---")

        # SECTION C: ADD NEW PRODUCT WITH CATEGORY
        st.subheader("➕ Add Brand New Product to Inventory")
        with st.form("add_product_form", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            p_name = col_a.text_input("Product Name")
            p_sku = col_b.text_input("SKU / Item Code")

            p_cat_select = col_a.selectbox("Category (Select Existing)", existing_cats)
            p_custom_cat = col_b.text_input("Or Type New Category (Optional)", placeholder="e.g. Dosing Cups & Funnels")

            p_landed_cost = col_a.number_input("Landed Cost w/ Packaging ($)", min_value=0.0, step=0.50)
            p_default_price = col_b.number_input("Default Set Selling Price ($)", min_value=0.0, step=0.50)
            p_stock = col_a.number_input("Initial Stock", min_value=0, step=1)

            submit = st.form_submit_button("Add New Product")
            if submit:
                if p_name.strip():
                    if p_name.strip() in inv_df["name"].astype(str).values:
                        st.error("A product with this name already exists in Google Sheets.")
                    else:
                        final_add_cat = p_custom_cat.strip() if p_custom_cat.strip() else p_cat_select
                        next_id = int(inv_df["id"].max() + 1) if not inv_df.empty and "id" in inv_df.columns else 1
                        new_row = {
                            "id": next_id, "name": p_name.strip(), "sku": p_sku.strip(),
                            "category": final_add_cat, "landed_cost": p_landed_cost, 
                            "default_price": p_default_price, "stock": p_stock
                        }
                        
                        st.session_state["products_df"] = pd.concat([st.session_state["products_df"], pd.DataFrame([new_row])], ignore_index=True)

                        payload = {
                            "action": "addProduct",
                            "row": [next_id, p_name.strip(), p_sku.strip(), final_add_cat, p_landed_cost, p_default_price, p_stock]
                        }
                        send_to_google_sheet(payload)

                        st.toast(f"Added {p_name} to Inventory!", icon="🎉")
                        st.rerun()
                else:
                    st.warning("Please enter a valid product name.")

        if not inv_df.empty:
            st.markdown("---")
            st.subheader("Current Stock & Pricing")
            st.dataframe(inv_df, width="stretch")

    # -------------------------------------------------------------------
    # TAB 3: LOG SALES WITH CATEGORY FILTER
    # -------------------------------------------------------------------
    with tabs[2]:
        st.header("Record a NawatCore Transaction")
        products_df = load_products_df()

        if not products_df.empty:
            st.subheader("🔍 Narrow Search by Category")
            available_categories = ["All Categories"] + sorted(list(products_df["category"].dropna().unique()))
            selected_cat_filter = st.selectbox("Filter Product List by Category", available_categories)

            if selected_cat_filter != "All Categories":
                filtered_products_df = products_df[products_df["category"] == selected_cat_filter]
            else:
                filtered_products_df = products_df

            if not filtered_products_df.empty:
                product_options = {
                    f"[{row['category']}] {row['name']} (Stock: {row['stock']} | Set Price: ${row['default_price']:.2f})": row
                    for _, row in filtered_products_df.iterrows()
                }
                selected_option = st.selectbox("Select Item to Sell", list(product_options.keys()))
                item = product_options[selected_option]

                col1, col2 = st.columns(2)

                with col1:
                    sale_qty = st.number_input("Quantity Sold", min_value=1, max_value=int(item["stock"]) if item["stock"] > 0 else 1, step=1)
                    actual_unit_price = st.number_input("Actual Sale Price per Unit ($)", min_value=0.0, value=float(item["default_price"]), step=0.50)
                    sale_type = st.radio("Sale Channel", ["Local", "Online"], horizontal=True)
                    shipping_cost = 0.0
                    if sale_type == "Online":
                        shipping_cost = st.number_input("Shipping Paid by You ($)", min_value=0.0, value=0.0, step=0.50)

                with col2:
                    payment_method = st.selectbox("Payment Method", ["Cash", "Zelle", "Venmo", "Apple Pay", "Cash App", "Other"])
                    transaction_date = st.date_input("Transaction Date", datetime.now())
                    transaction_time = st.time_input("Transaction Time", datetime.now().time())
                    sale_timestamp = datetime.combine(transaction_date, transaction_time).strftime("%Y-%m-%d %H:%M:%S")

                sale_notes = st.text_input("Order Notes / Comments (Optional)", placeholder="Customer name, pickup info, etc.")

                gross_total = sale_qty * actual_unit_price
                net_total = gross_total - shipping_cost
                total_landed_cost = sale_qty * float(item["landed_cost"])
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
                        sales_df_mem = load_sales_df()
                        next_sale_id = int(sales_df_mem["id"].max() + 1) if not sales_df_mem.empty and "id" in sales_df_mem.columns else 1

                        new_sale_row = {
                            "id": next_sale_id, "product_id": int(item["id"]), "quantity": sale_qty,
                            "unit_sale_price": actual_unit_price, "gross_total": gross_total,
                            "sale_type": sale_type, "shipping_cost": shipping_cost, "net_total": net_total,
                            "landed_cost_total": total_landed_cost, "net_profit": net_profit,
                            "payment_method": payment_method, "sale_date": sale_timestamp, "notes": sale_notes.strip()
                        }

                        st.session_state["sales_df"] = pd.concat([st.session_state["sales_df"], pd.DataFrame([new_sale_row])], ignore_index=True)
                        p_idx = st.session_state["products_df"].index[st.session_state["products_df"]["id"] == int(item["id"])].tolist()
                        if p_idx:
                            st.session_state["products_df"].at[p_idx[0], "stock"] -= sale_qty

                        payload = {
                            "action": "addSale",
                            "product_id": int(item["id"]),
                            "qty": sale_qty,
                            "row": [
                                next_sale_id, int(item["id"]), sale_qty, actual_unit_price,
                                gross_total, sale_type, shipping_cost, net_total,
                                total_landed_cost, net_profit, payment_method,
                                sale_timestamp, sale_notes.strip()
                            ]
                        }
                        send_to_google_sheet(payload)

                        st.toast("Sale logged permanently!", icon="🛒")
                        st.rerun()
            else:
                st.warning("No products found in this category.")
        else:
            st.info("Add products to inventory before logging sales.")

    # -------------------------------------------------------------------
    # TAB 4: SALES HISTORY, FILTERS & EDIT TRANSACTIONS
    # -------------------------------------------------------------------
    with tabs[3]:
        st.header("NawatCore Sales Ledger & Order Editing")
        products_df = load_products_df()
        sales_raw_df = load_sales_df()

        if not sales_raw_df.empty and not products_df.empty and "product_id" in sales_raw_df.columns:
            sales_raw_df["product_id"] = pd.to_numeric(sales_raw_df["product_id"], errors='coerce').fillna(0).astype(int)
            products_df["id"] = pd.to_numeric(products_df["id"], errors='coerce').fillna(0).astype(int)

            sales_merged = sales_raw_df.merge(
                products_df[["id", "name", "landed_cost"]], left_on="product_id", right_on="id", how="left", suffixes=("", "_prod")
            ).rename(columns={
                "id": "Sale ID", "sale_date": "Date & Time", "name": "Product",
                "quantity": "Qty", "unit_sale_price": "Sold Price/Unit",
                "gross_total": "Gross Rev", "sale_type": "Type",
                "shipping_cost": "Shipping Cost", "net_total": "Net Revenue",
                "net_profit": "Net Profit", "payment_method": "Payment Method",
                "notes": "Comments / Notes"
            })
            sales_merged["Product"] = sales_merged["Product"].fillna("Unknown Product")

            sales_merged['parsed_dt'] = pd.to_datetime(sales_merged['Date & Time'], errors='coerce')
            sales_merged['parsed_date'] = sales_merged['parsed_dt'].dt.date

            st.subheader("🔍 Filter Sales Ledger")
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)

            valid_dates = sales_merged['parsed_date'].dropna()
            min_date = valid_dates.min() if not valid_dates.empty else datetime.now().date()
            max_date = valid_dates.max() if not valid_dates.empty else datetime.now().date()

            with col_f1:
                start_date = st.date_input("Start Date", min_date)
                end_date = st.date_input("End Date", max_date)

            all_products = ["All Products"] + sorted(list(sales_merged['Product'].dropna().unique()))
            with col_f2:
                selected_prod = st.selectbox("Product", all_products)

            with col_f3:
                selected_channel = st.selectbox("Sale Channel", ["All Channels", "Local", "Online"])

            all_payments = ["All Payment Methods"] + sorted(list(sales_merged['Payment Method'].dropna().unique()))
            with col_f4:
                selected_payment = st.selectbox("Payment Method", all_payments)

            filtered_df = sales_merged.copy()
            
            if not filtered_df['parsed_date'].isna().all():
                filtered_df = filtered_df[
                    (filtered_df['parsed_date'].isna()) | 
                    ((filtered_df['parsed_date'] >= start_date) & (filtered_df['parsed_date'] <= end_date))
                ]

            if selected_prod != "All Products":
                filtered_df = filtered_df[filtered_df['Product'] == selected_prod]
            if selected_channel != "All Channels":
                filtered_df = filtered_df[filtered_df['Type'] == selected_channel]
            if selected_payment != "All Payment Methods":
                filtered_df = filtered_df[filtered_df['Payment Method'] == selected_payment]

            f_rev = filtered_df['Gross Rev'].sum() if not filtered_df.empty else 0.0
            f_profit = filtered_df['Net Profit'].sum() if not filtered_df.empty else 0.0
            f_units = filtered_df['Qty'].sum() if not filtered_df.empty else 0

            st.markdown(
                f"**Filter Summary:** Found **{len(filtered_df)}** transactions | **{f_units}** Units Sold | **${f_rev:,.2f}** Gross Rev | **${f_profit:,.2f}** Net Profit"
            )

            display_ledger = filtered_df.copy()
            display_ledger["Margin %"] = (
                (display_ledger["Net Profit"] / display_ledger["Gross Rev"].replace(0, 1)) * 100
            ).round(1).astype(str) + "%"

            cols_to_show = [
                'Sale ID', 'Date & Time', 'Product', 'Qty', 'Sold Price/Unit',
                'Gross Rev', 'Shipping Cost', 'Net Revenue', 'Net Profit', 'Margin %', 
                'Payment Method', 'Type', 'Comments / Notes'
            ]
            st.dataframe(display_ledger[cols_to_show], width="stretch")

            st.markdown("---")

            # EDIT TRANSACTION SECTION
            st.subheader("✏️ Modify / Edit Existing Sale Record")
            st.caption("Select a sale below to adjust pricing, quantities, notes, or payment methods.")

            sale_list = {
                f"ID #{row['Sale ID']} - {row['Product']} (Qty: {row['Qty']} | ${row['Gross Rev']:.2f} on {row['Date & Time']})": row
                for _, row in sales_merged.iterrows()
            }
            selected_sale_label = st.selectbox("Select Sale Record to Modify", list(sale_list.keys()))
            s_edit = sale_list[selected_sale_label]

            with st.form("edit_sale_form"):
                ec1, ec2 = st.columns(2)

                with ec1:
                    e_qty = ec1.number_input("Quantity Sold", min_value=1, value=int(s_edit["Qty"]), step=1)
                    e_unit_price = ec1.number_input("Sale Price per Unit ($)", min_value=0.0, value=float(s_edit["Sold Price/Unit"]), step=0.50)
                    e_type = ec1.radio("Sale Channel", ["Local", "Online"], index=0 if s_edit["Type"] == "Local" else 1, horizontal=True)
                    
                    e_shipping = 0.0
                    if e_type == "Online":
                        e_shipping = ec1.number_input("Shipping Paid by You ($)", min_value=0.0, value=float(s_edit["Shipping Cost"]), step=0.50)

                with ec2:
                    pay_options = ["Cash", "Zelle", "Venmo", "Apple Pay", "Cash App", "Other"]
                    default_pay_idx = pay_options.index(s_edit["Payment Method"]) if s_edit["Payment Method"] in pay_options else 0
                    e_payment = ec2.selectbox("Payment Method", pay_options, index=default_pay_idx)
                    
                    parsed_dt = pd.to_datetime(s_edit["Date & Time"], errors='coerce')
                    if pd.isna(parsed_dt):
                        parsed_dt = datetime.now()

                    e_date = ec2.date_input("Transaction Date", parsed_dt.date())
                    e_time = ec2.time_input("Transaction Time", parsed_dt.time())
                    e_timestamp = datetime.combine(e_date, e_time).strftime("%Y-%m-%d %H:%M:%S")

                e_notes = st.text_input("Comments / Notes", value=str(s_edit["Comments / Notes"]))

                e_gross = e_qty * e_unit_price
                e_net = e_gross - e_shipping
                e_landed_total = e_qty * float(s_edit["landed_cost"]) if pd.notna(s_edit["landed_cost"]) else 0.0
                e_profit = e_net - e_landed_total
                qty_difference = e_qty - int(s_edit["Qty"])

                btn_edit = st.form_submit_button("💾 Save Updated Sale Record", type="primary")
                if btn_edit:
                    s_idx = st.session_state["sales_df"].index[st.session_state["sales_df"]["id"] == int(s_edit["Sale ID"])].tolist()
                    if s_idx:
                        st.session_state["sales_df"].loc[s_idx[0]] = [
                            int(s_edit["Sale ID"]), int(s_edit["product_id"]), int(e_qty), float(e_unit_price),
                            float(e_gross), str(e_type), float(e_shipping), float(e_net),
                            float(e_landed_total), float(e_profit), str(e_payment),
                            str(e_timestamp), str(e_notes).strip()
                        ]
                        st.session_state["sales_df"]["id"] = pd.to_numeric(st.session_state["sales_df"]["id"], errors='coerce').fillna(0).astype(int)
                        st.session_state["sales_df"]["product_id"] = pd.to_numeric(st.session_state["sales_df"]["product_id"], errors='coerce').fillna(0).astype(int)
                        st.session_state["sales_df"]["quantity"] = pd.to_numeric(st.session_state["sales_df"]["quantity"], errors='coerce').fillna(0).astype(int)

                    if qty_difference != 0:
                        p_idx = st.session_state["products_df"].index[st.session_state["products_df"]["id"] == int(s_edit["product_id"])].tolist()
                        if p_idx:
                            st.session_state["products_df"].at[p_idx[0], "stock"] -= qty_difference

                    payload = {
                        "action": "editSale",
                        "sale_id": int(s_edit["Sale ID"]),
                        "product_id": int(s_edit["product_id"]),
                        "qty_diff": qty_difference,
                        "row": [
                            int(s_edit["Sale ID"]), int(s_edit["product_id"]), e_qty, e_unit_price,
                            e_gross, e_type, e_shipping, e_net,
                            e_landed_total, e_profit, e_payment,
                            e_timestamp, e_notes.strip()
                        ]
                    }
                    send_to_google_sheet(payload)

                    st.toast(f"Updated Sale ID #{s_edit['Sale ID']}!", icon="✏️")
                    st.rerun()
        else:
            st.info("No sales recorded yet.")