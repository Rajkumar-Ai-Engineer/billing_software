import streamlit as st
import pandas as pd
import os
import base64
import qrcode
import barcode
from barcode.writer import ImageWriter
import io
import datetime
import urllib.parse
import streamlit.components.v1 as components

st.set_page_config(page_title="Sri Dhanam Motors - Billing & Inventory", layout="wide")

# -------------------- CONFIGURATION --------------------
WEBSITE_URL = "https://www.sridhanammotors.com"

# -------------------- CUSTOM CSS --------------------
st.markdown("""
    <style>
        .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
            font-size: 18px !important;
            font-weight: 800 !important;
            color: #1A365D !important;
        }
        .stButton>button {
            border-radius: 8px !important;
            font-weight: bold !important;
            font-size: 16px !important;
        }
    </style>
""", unsafe_allow_html=True)

# -------------------- FILE STORAGE SETUP --------------------
PRODUCT_FILE = "products_master.csv"
INVOICE_FILE = "invoices.csv"

if os.path.exists(PRODUCT_FILE):
    products_df = pd.read_csv(PRODUCT_FILE)
    if "Cost Price" not in products_df.columns:
        if "Price" in products_df.columns:
            products_df["Cost Price"] = products_df["Price"]
        else:
            products_df["Cost Price"] = 25000.0
    if "Stock Qty" not in products_df.columns:
        products_df["Stock Qty"] = 10
    products_df.to_csv(PRODUCT_FILE, index=False)
else:
    products_df = pd.DataFrame([
        {"Part No": "SDM-MOT-250", "Product Name": "EV Motor 250W", "HSN": "8501", "Cost Price": 5000.0, "GST %": 18, "Stock Qty": 10, "Category": "Spare Parts"},
        {"Part No": "SDM0010", "Product Name": "EV Battery Pack 48V", "HSN": "8507", "Cost Price": 25000.0, "GST %": 18, "Stock Qty": 5, "Category": "Spare Parts"},
        {"Part No": "SDM-VEH-JHEV", "Product Name": "JHEV EV Scooter", "HSN": "8711", "Cost Price": 65000.0, "GST %": 5, "Stock Qty": 3, "Category": "Vehicle Sales"}
    ])
    products_df.to_csv(PRODUCT_FILE, index=False)

# -------------------- HEADER & LOGO --------------------
col_logo, col_title = st.columns([1, 4])

logo_path = None
possible_logos = ["logo.jpg.png", "logo.png", "logo.jpg", "logo.jpeg", "logo"]
for filename in possible_logos:
    if os.path.exists(filename):
        logo_path = filename
        break

def get_base64_image(image_path):
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return ""

logo_base64 = get_base64_image(logo_path)

with col_logo:
    if logo_path and os.path.exists(logo_path):
        st.image(logo_path, width=140)
    else:
        st.info("📌 Add Logo File")

with col_title:
    st.markdown("""
        <div style='text-align: left;'>
            <h1 style='color: #2E7D32; margin-bottom: 0; font-size: 34px;'>SRI DHANAM MOTORS</h1>
            <h3 style='color: #2B6CB0; margin-top: 2px; font-size: 18px;'>⚡ SALES, SERVICES & SPARES</h3>
            <p style='font-size: 13px; color: #4A5568;'>
                <b>📍 Near RTO Office Mobirippatti, Harur(Tk), Dharmapuri(Dt) - 636903</b><br>
                <b>📞 Phone:</b> +91 9344885449, +91 8428544972 | <b>GSTIN:</b> Applied (A/F)
            </p>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# -------------------- NAVIGATION TABS --------------------
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "🧾 INVOICE & BILLING", 
    "🏷️ PRODUCT BARCODE / QR",
    "🔋 BATTERY SERIAL QR", 
    "⚙️ PRODUCT & STOCK MASTER", 
    "📊 SALES REPORTS",
    "👷 WORKER ATTENDANCE",
    "💸 DAILY EXPENSES",
    "📥 INWARD PURCHASES"
])

# -------------------- HELPER FUNCTIONS FOR BARCODE & QR --------------------
def generate_barcode_base64(code_text):
    try:
        CODE128 = barcode.get_barcode_class('code128')
        rv = io.BytesIO()
        CODE128(str(code_text), writer=ImageWriter()).write(rv)
        return base64.b64encode(rv.getvalue()).decode()
    except Exception:
        return ""

def generate_qr_base64(qr_text):
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(qr_text)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def get_next_invoice_no(prefix="SDM"):
    import re
    if os.path.exists(INVOICE_FILE):
        inv_df = pd.read_csv(INVOICE_FILE)
        if not inv_df.empty:
            nums = []
            for inv in inv_df["Invoice No"]:
                m = re.match(r"^SDM(\d+)$", str(inv).strip(), re.IGNORECASE)
                if m:
                    try:
                        nums.append(int(m.group(1)))
                    except:
                        pass
            if nums:
                next_num = max(nums) + 1
                return f"SDM{str(next_num).zfill(4)}"
    return "SDM0001"

# -------------------- TAB 1: INVOICE & BILLING --------------------
with tab1:
    if 'bill_items' not in st.session_state:
        st.session_state.bill_items = []
    if 'cust_type_locked' not in st.session_state:
        st.session_state.cust_type_locked = False
    if 'locked_type' not in st.session_state:
        st.session_state.locked_type = "Customer"
    if 'print_html_content' not in st.session_state:
        st.session_state.print_html_content = None

    if 'cust_name' not in st.session_state:
        st.session_state.cust_name = ""
    if 'cust_mobile' not in st.session_state:
        st.session_state.cust_mobile = ""
    if 'dealer_address' not in st.session_state:
        st.session_state.dealer_address = ""

    col_cat1, col_cat2, col_cat3 = st.columns(3)
    with col_cat1:
        bill_category = st.selectbox("📌 Select Billing Category:", ["Spare Parts", "Service", "Vehicle Sales"])
    with col_cat2:
        buyer_type = st.selectbox(
            "👤 Select Pricing Type:", 
            ["Customer", "Dealer"], 
            disabled=st.session_state.cust_type_locked,
            index=0 if st.session_state.locked_type == "Customer" else 1
        )
    with col_cat3:
        gst_option = st.selectbox("🧾 GST Mode:", ["With GST (Tax Invoice)", "Without GST (Estimate / Cash)"])

    is_gst_bill = (gst_option == "With GST (Tax Invoice)")
    active_buyer_type = st.session_state.locked_type if st.session_state.cust_type_locked else buyer_type

    st.subheader(f"📄 New {'Tax Invoice' if is_gst_bill else 'Estimate'} - {bill_category} ({active_buyer_type})")
    
    inv_prefix = "SDM"
    auto_inv_no = get_next_invoice_no(inv_prefix)

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        dealer_name = st.text_input("👤 Customer / Dealer Name:", value=st.session_state.cust_name)
        cust_mobile = st.text_input("📱 Customer Mobile No:", value=st.session_state.cust_mobile)
        dealer_address = st.text_area("📍 Customer Address:", value=st.session_state.dealer_address)

    with col_c2:
        invoice_no = st.text_input("🔖 Invoice / Bill No (Auto):", auto_inv_no)
        inv_date = st.date_input("📅 Date")
        gstin = st.text_input("🏢 GSTIN (Optional):").strip().upper()

    st.markdown("---")
    st.markdown("### ☑️ Select Products to Add in Bill (Tick Case)")
    st.caption("Tick the box to add items directly to the bill. Untick to remove.")

    products_df = pd.read_csv(PRODUCT_FILE)
    if "Category" in products_df.columns:
        if bill_category == "Spare Parts":
            category_products = products_df[products_df["Category"] == "Spare Parts"]
        elif bill_category == "Service":
            category_products = products_df[products_df["Category"] != "Vehicle Sales"]
        elif bill_category == "Vehicle Sales":
            category_products = products_df[products_df["Category"] != "Service"]
        else:
            category_products = products_df[products_df["Category"] == bill_category]
    else:
        category_products = products_df

    col_srch, col_flt = st.columns([2, 1])
    with col_srch:
        search_query = st.text_input("🔍 Quick Search Item / Part No:", "", key="app_search_filter").strip()
    with col_flt:
        view_mode = st.radio("Show:", ["All Items", "Ticked Only"], horizontal=True, key="view_mode_radio")

    margin_percent = 0.40 if active_buyer_type == "Dealer" else 0.80

    if search_query:
        match_mask = (
            category_products["Product Name"].astype(str).str.contains(search_query, case=False, na=False) |
            category_products["Part No"].astype(str).str.contains(search_query, case=False, na=False)
        )
        display_df = category_products[match_mask]
    else:
        display_df = category_products

    ticked_part_nos = [item["Part No"] for item in st.session_state.bill_items]

    if view_mode == "Ticked Only":
        display_df = display_df[display_df["Part No"].astype(str).isin(ticked_part_nos)]

    if display_df.empty:
        st.info("No matching products found.")
    else:
        hdr_cols = st.columns([0.8, 1.4, 2.6, 1.0, 1.2, 1.2, 1.2])
        hdr_cols[0].markdown("**Tick (☑)**")
        hdr_cols[1].markdown("**Part No**")
        hdr_cols[2].markdown("**Product Name**")
        hdr_cols[3].markdown("**Stock**")
        hdr_cols[4].markdown("**Price (₹)**")
        hdr_cols[5].markdown("**Qty**")
        hdr_cols[6].markdown("**Total (₹)**")

        for _, row in display_df.iterrows():
            p_code = str(row["Part No"])
            p_name = str(row["Product Name"])
            p_stock = int(row["Stock Qty"])
            p_cost = float(row["Cost Price"])
            p_gst = float(row["GST %"])
            p_price = round(p_cost + (p_cost * margin_percent), 2)

            is_currently_ticked = p_code in ticked_part_nos
            existing_item = next((i for i in st.session_state.bill_items if i["Part No"] == p_code), None)
            current_qty = existing_item["Qty"] if existing_item else 1

            r_cols = st.columns([0.8, 1.4, 2.6, 1.0, 1.2, 1.2, 1.2])

            is_out_of_stock = (p_stock <= 0)

            ticked = r_cols[0].checkbox(
                "Add", 
                value=is_currently_ticked, 
                key=f"tick_{p_code}",
                disabled=is_out_of_stock,
                label_visibility="collapsed"
            )
            r_cols[1].write(f"**{p_code}**")
            r_cols[2].write(p_name)
            
            if is_out_of_stock:
                r_cols[3].markdown("<span style='color:red;font-weight:bold;'>Out</span>", unsafe_allow_html=True)
            elif p_stock <= 3:
                r_cols[3].markdown(f"<span style='color:orange;font-weight:bold;'>{p_stock}</span>", unsafe_allow_html=True)
            else:
                r_cols[3].markdown(f"<span style='color:green;font-weight:bold;'>{p_stock}</span>", unsafe_allow_html=True)

            r_cols[4].write(f"₹{p_price:,.2f}")

            new_qty = r_cols[5].number_input(
                "Qty", 
                min_value=1, 
                max_value=max(1, p_stock), 
                value=min(current_qty, max(1, p_stock)),
                key=f"qty_{p_code}",
                disabled=not ticked or is_out_of_stock,
                label_visibility="collapsed"
            )

            line_tot = p_price * new_qty if ticked else 0.0
            r_cols[6].write(f"₹{line_tot:,.2f}" if ticked else "—")

            if ticked and not is_currently_ticked:
                if not st.session_state.cust_type_locked:
                    st.session_state.cust_type_locked = True
                    st.session_state.locked_type = buyer_type
                st.session_state.bill_items.append({
                    "Part No": p_code,
                    "Product Name": p_name,
                    "Price (₹)": p_price,
                    "Qty": int(new_qty),
                    "Sub Total (₹)": round(p_price * new_qty, 2),
                    "Orig GST %": p_gst
                })
                st.rerun()
            elif not ticked and is_currently_ticked:
                st.session_state.bill_items = [i for i in st.session_state.bill_items if i["Part No"] != p_code]
                if len(st.session_state.bill_items) == 0:
                    st.session_state.cust_type_locked = False
                st.rerun()
            elif ticked and is_currently_ticked and existing_item:
                if existing_item["Qty"] != int(new_qty):
                    existing_item["Qty"] = int(new_qty)
                    existing_item["Sub Total (₹)"] = round(p_price * new_qty, 2)
                    st.rerun()

    if st.session_state.bill_items:
        st.markdown("### 📋 Items Added in Current Bill")

        calculated_items = []
        for item in st.session_state.bill_items:
            base_amt = item["Sub Total (₹)"]
            gst_rate = item["Orig GST %"] if is_gst_bill else 0.0
            gst_amt = base_amt * (gst_rate / 100.0) if is_gst_bill else 0.0
            tot_amt = base_amt + gst_amt
            
            calculated_items.append({
                "Part No": item["Part No"],
                "Product Name": item["Product Name"],
                "Price (₹)": item["Price (₹)"],
                "Qty": item["Qty"],
                "Sub Total (₹)": base_amt,
                "GST %": f"{int(gst_rate)}%",
                "GST Amt (₹)": round(gst_amt, 2),
                "Total (₹)": round(tot_amt, 2)
            })

        headers = ["S.No", "Part No", "Product Name", "Price (₹)", "Qty", "Sub Total (₹)", "GST %", "GST Amt (₹)", "Total (₹)", "REMOVE ITEM"]
        cols = st.columns([0.6, 1.2, 2.5, 1.2, 0.8, 1.3, 0.9, 1.3, 1.3, 1.5])
        
        for col, h in zip(cols, headers):
            col.markdown(f"**{h}**")

        st.divider()

        for idx, item in enumerate(calculated_items):
            r_cols = st.columns([0.6, 1.2, 2.5, 1.2, 0.8, 1.3, 0.9, 1.3, 1.3, 1.5])
            
            r_cols[0].write(f"**{idx + 1}**")
            r_cols[1].write(item["Part No"])
            r_cols[2].write(f"**{item['Product Name']}**")
            r_cols[3].write(f"₹{item['Price (₹)']:,.2f}")
            r_cols[4].write(f"**{item['Qty']}**")
            r_cols[5].write(f"₹{item['Sub Total (₹)']:,.2f}")
            r_cols[6].write(item["GST %"])
            r_cols[7].write(f"₹{item['GST Amt (₹)']:,.2f}")
            r_cols[8].write(f"**₹{item['Total (₹)']:,.2f}**")
            
            if r_cols[9].button("🗑 DELETE", key=f"del_btn_{idx}"):
                st.session_state.bill_items.pop(idx)
                if len(st.session_state.bill_items) == 0:
                    st.session_state.cust_type_locked = False
                st.rerun()

        st.markdown("---")
        
        df_calc = pd.DataFrame(calculated_items)
        total_base_price = df_calc["Sub Total (₹)"].sum()
        total_gst = df_calc["GST Amt (₹)"].sum()
        grand_total = total_base_price + total_gst

        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.markdown(f"#### 💵 **Sub Total:** ₹ {total_base_price:,.2f}")
        with col_t2:
            st.markdown(f"#### 🏛️ **GST Amount:** ₹ {total_gst:,.2f}")
        with col_t3:
            st.markdown(f"### 💰 **Grand Total:** ₹ {grand_total:,.2f}")

        def deduct_stock_and_save():
            master_df = pd.read_csv(PRODUCT_FILE)
            for item in st.session_state.bill_items:
                part_no = item["Part No"]
                sold_qty = item["Qty"]
                
                mask = master_df["Part No"].astype(str) == str(part_no)
                master_df.loc[mask, "Stock Qty"] = master_df.loc[mask, "Stock Qty"] - sold_qty

            master_df.to_csv(PRODUCT_FILE, index=False)

            new_inv = pd.DataFrame([{
                "Invoice No": invoice_no,
                "Date": str(inv_date),
                "Category": bill_category,
                "Type": st.session_state.locked_type,
                "GST Mode": gst_option,
                "Customer": dealer_name,
                "Mobile": cust_mobile,
                "Address": dealer_address,
                "GSTIN": gstin,
                "Base Total": total_base_price,
                "GST Amount": total_gst,
                "Grand Total": grand_total
            }])
            if os.path.exists(INVOICE_FILE):
                existing_df = pd.read_csv(INVOICE_FILE)
                existing_df = existing_df[existing_df["Invoice No"] != invoice_no]
                updated_df = pd.concat([existing_df, new_inv], ignore_index=True)
                updated_df.to_csv(INVOICE_FILE, index=False)
            else:
                new_inv.to_csv(INVOICE_FILE, index=False)

            st.session_state.cust_name = ""
            st.session_state.cust_mobile = ""
            st.session_state.dealer_address = ""

        def build_print_html(bill_title_text):
            qr_b64_inv = generate_qr_base64(f"{WEBSITE_URL}?invoice={invoice_no}")
            current_time_str = datetime.datetime.now().strftime("%I:%M %p")

            items_rows = ""
            for idx, item in enumerate(calculated_items):
                items_rows += f"<tr><td>{idx + 1}</td><td>{item['Part No']}</td><td>{item['Product Name']}</td><td>₹{item['Price (₹)']:,.2f}</td><td>{item['Qty']}</td><td>₹{item['Sub Total (₹)']:,.2f}</td><td>{item['GST %']}</td><td>₹{item['GST Amt (₹)']:,.2f}</td><td>₹{item['Total (₹)']:,.2f}</td></tr>"
            
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="max-height: 75px; float: left; margin-right: 15px;">' if logo_base64 else ''
            qr_html = f'<img src="data:image/png;base64,{qr_b64_inv}" style="max-height: 85px; float: right;">'
            
            brand_subtitle = "AUTHORIZED JHEV MOTORS DEALER" if bill_category == "Vehicle Sales" else "SALES, SERVICES & SPARES"

            return f"""
            <html>
            <head>
                <style>
                    body {{ font-family: 'Arial', sans-serif; padding: 20px; color: #000; }}
                    .header-container {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 15px; }}
                    .company-title {{ color: #2E7D32; margin: 0; font-size: 22px; font-weight: bold; }}
                    .bill-info {{ display: flex; justify-content: space-between; margin-bottom: 15px; font-size: 13px; background: #f9f9f9; padding: 10px; border: 1px solid #000; color: #000; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                    th, td {{ border: 1px solid #000; padding: 8px; text-align: center; font-size: 13px; color: #000 !important; font-weight: bold; }}
                    th {{ background-color: #dcdcdc !important; color: #000 !important; font-weight: bold; }}
                    .summary-container {{ display: flex; justify-content: space-between; align-items: flex-end; margin-top: 20px; }}
                    .signature-box {{ width: 40%; text-align: right; font-size: 13px; font-weight: bold; padding-top: 40px; }}
                    .summary-box {{ width: 45%; font-size: 14px; border: 1px solid #000; padding: 10px; background-color: #f9f9f9; }}
                    .summary-box div {{ display: flex; justify-content: space-between; margin-bottom: 5px; }}
                    .grand-total {{ font-weight: bold; font-size: 16px; color: #000; border-top: 2px solid #000; padding-top: 5px; margin-top: 5px; }}
                </style>
            </head>
            <body>
                <div class="header-container">
                    <div style="display: flex; align-items: center;">
                        {logo_html}
                        <div>
                            <h2 class="company-title">SRI DHANAM MOTORS</h2>
                            <span style="font-size: 12px; font-weight: bold; color: #1A365D;">{brand_subtitle}</span>
                            <p style="margin: 2px 0; font-size: 11px;">
                                Near RTO Office Mobirippatti, Harur(Tk), Dharmapuri(Dt) - 636903<br>
                                <b>Ph:</b> +91 9344885449, +91 8428544972 | <b>GSTIN:</b> Applied (A/F)
                            </p>
                        </div>
                    </div>
                    <div>
                        {qr_html}
                    </div>
                </div>

                <div class="bill-info">
                    <div>
                        <b>Billed To:</b> {dealer_name} (Ph: {cust_mobile})<br>
                        <b>Address:</b> {dealer_address}<br>
                        <b>GSTIN:</b> {gstin if gstin else 'N/A'}
                    </div>
                    <div style="text-align: right;">
                        <b>S:No:</b> {invoice_no}<br>
                        <b>Date:</b> {inv_date} &nbsp;|&nbsp; {current_time_str}<br>
                        <b>Category:</b> {bill_category.upper()}
                    </div>
                </div>
                
                <table>
                    <tr>
                        <th>S.No</th><th>Part No</th><th>Product Name</th><th>Price</th><th>Qty</th><th>Sub Total</th><th>GST %</th><th>GST Amt</th><th>Total (₹)</th>
                    </tr>
                    {items_rows}
                </table>
                
                <div class="summary-container">
                    <div class="signature-box">
                        <b>Signature</b>
                    </div>
                    <div class="summary-box">
                        <div><span>Base Amount:</span> <span>₹{total_base_price:,.2f}</span></div>
                        <div><span>GST Amount:</span> <span>₹{total_gst:,.2f}</span></div>
                        <div class="grand-total"><span>Grand Total:</span> <span>₹{grand_total:,.2f}</span></div>
                    </div>
                </div>

                <script>
                    window.print();
                </script>
            </body>
            </html>
            """

        col_b1, col_b2, col_b3, col_b4 = st.columns([1.5, 1.5, 1.5, 1])
        
        with col_b1:
            if st.button("🖨️ SAVE & PRINT INVOICE", type="primary"):
                deduct_stock_and_save()
                title_str = "TAX INVOICE" if is_gst_bill else "ESTIMATE"
                st.session_state.print_html_content = build_print_html(title_str)
                st.success("✅ Invoice Saved Successfully!")
                st.rerun()

        with col_b2:
            if st.button("📄 PRINT ESTIMATE"):
                title_str = "ESTIMATE"
                st.session_state.print_html_content = build_print_html(title_str)

        with col_b3:
            if st.button("💬 SAVE & SHARE WHATSAPP"):
                deduct_stock_and_save()
                
                whatsapp_message = f"Hello {dealer_name},\nThank you for shopping at Sri Dhanam Motors!\nInvoice No: {invoice_no}\nGrand Total: ₹{grand_total:,.2f}\nVisit us again!"
                encoded_message = urllib.parse.quote(whatsapp_message)
                
                clean_mobile = "".join(filter(str.isdigit, str(cust_mobile)))
                if len(clean_mobile) == 10:
                    clean_mobile = "91" + clean_mobile
                
                whatsapp_url = f"https://wa.me/{clean_mobile}?text={encoded_message}"
                
                js_code = f"""
                <script>
                    window.open('{whatsapp_url}', '_blank');
                </script>
                """
                components.html(js_code, height=0, width=0)
                st.success("✅ Bill Saved & WhatsApp Opening...")
                st.rerun()

        with col_b4:
            if st.button("🔄 RESET"):
                st.session_state.bill_items = []
                st.session_state.cust_type_locked = False
                st.session_state.cust_name = ""
                st.session_state.cust_mobile = ""
                st.session_state.dealer_address = ""
                st.rerun()

        if st.session_state.print_html_content:
            components.html(st.session_state.print_html_content, height=0, width=0)

# -------------------- TAB 2: PRODUCT BARCODE / QR --------------------
with tab2:
    st.subheader("🏷️ Product Barcode & QR Generator")
    if os.path.exists(PRODUCT_FILE):
        p_df = pd.read_csv(PRODUCT_FILE)
        selected_part = st.selectbox("Select Product to Generate Label", p_df["Part No"].tolist())
        if selected_part:
            row_p = p_df[p_df["Part No"] == selected_part].iloc[0]
            st.write(f"**Product:** {row_p['Product Name']} | **Part No:** {row_p['Part No']} | **Cost:** ₹{row_p.get('Cost Price', 0)}")
            col_qr, col_bar = st.columns(2)
            with col_qr:
                qr_b64 = generate_qr_base64(f"PART:{row_p['Part No']}|NAME:{row_p['Product Name']}")
                st.markdown(f'<img src="data:image/png;base64,{qr_b64}" width="150">', unsafe_allow_html=True)
                st.caption("QR Code (Part No & Name)")
            with col_bar:
                bar_b64 = generate_barcode_base64(str(row_p['Part No']))
                st.markdown(f'<img src="data:image/png;base64,{bar_b64}" width="220">', unsafe_allow_html=True)
                st.caption("Barcode (Code 128)")

# -------------------- TAB 3: BATTERY SERIAL QR --------------------
with tab3:
    st.subheader("🔋 Battery Serial & QR Generator")
    st.info("⚡ For full TVS LP 46 thermal printing and database tracking, also visit the FastAPI app at [http://127.0.0.1:8000/battery-qr](http://127.0.0.1:8000/battery-qr).")
    col_bt1, col_bt2, col_bt3 = st.columns(3)
    with col_bt1:
        b_type = st.selectbox("Battery Chemistry", ["LFP (Lithium Iron Phosphate)", "Li-Ion (Lithium-Ion)"])
    with col_bt2:
        b_volt = st.number_input("Voltage (V)", value=48.0, step=12.0)
    with col_bt3:
        b_ah = st.number_input("Capacity (Ah)", value=30.0, step=5.0)
    
    b_serial = f"SDM-BATT-{int(b_volt)}V{int(b_ah)}AH"
    if st.button("Generate Battery QR"):
        st.write(f"**Serial:** `{b_serial}`")
        qr_b64 = generate_qr_base64(f"SRI DHANAM MOTORS|SN:{b_serial}|{b_type}|{b_volt}V|{b_ah}Ah")
        st.markdown(f'<img src="data:image/png;base64,{qr_b64}" width="180">', unsafe_allow_html=True)

# -------------------- TAB 4: PRODUCT & STOCK MASTER --------------------
with tab4:
    st.subheader("⚙️ Product & Stock Master")
    if os.path.exists(PRODUCT_FILE):
        prods_master_df = pd.read_csv(PRODUCT_FILE)
        st.dataframe(prods_master_df, use_container_width=True)
    else:
        st.warning("No products file found.")

# -------------------- TAB 5: SALES REPORTS --------------------
with tab5:
    st.subheader("📊 Sales & Invoice Reports")
    if os.path.exists(INVOICE_FILE):
        invoices_data = pd.read_csv(INVOICE_FILE)
        st.dataframe(invoices_data, use_container_width=True)
    else:
        st.info("No invoices recorded yet.")

# -------------------- TAB 6: WORKER ATTENDANCE & SALARY --------------------
with tab6:
    st.subheader("👷 Worker Attendance & Month-End Salary")
    
    # Policy Banner
    st.markdown("""
        <div style="background-color: #EBF8FF; border-left: 5px solid #2B6CB0; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px;">
            <h4 style="color: #1A365D; margin: 0 0 6px 0;">📋 Shop Attendance & Salary Policy</h4>
            <p style="margin: 0; font-size: 14px; color: #2D3748;">
                • <b>1 Paid Leave Allowed Per Month:</b> Every worker gets 1 paid leave per month without salary deduction (e.g., A1 present 30 days &rarr; <b>Full Salary</b>, A2 present 29 days &rarr; <b>Full Salary</b>).<br>
                • <b>2+ Days Leave Deductions:</b> When a worker takes <b>2 days leave</b>, <b>1 day salary</b> is reduced (Formula: <code>Deduction Days = Total Leaves - 1</code>).
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    import calendar
    import sqlite3
    
    db_file = os.path.join(os.path.dirname(__file__), "sdm_billing", "data", "sdm.db")
    
    def get_sqlite():
        if os.path.exists(db_file):
            return sqlite3.connect(db_file)
        return None
    
    # Sub navigation
    att_subview = st.radio("Attendance Module", ["📅 Daily Attendance Register", "💰 Month-End Salary Calculation", "👥 Manage Workers"], horizontal=True)
    
    conn = get_sqlite()
    if conn is None:
        st.error("Database file not found at " + db_file)
    else:
        cur = conn.cursor()
        
        # Ensure tables exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                role TEXT DEFAULT 'Technician',
                monthly_salary REAL DEFAULT 15000.0,
                active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY,
                worker_id INTEGER NOT NULL,
                date DATE NOT NULL,
                day_name TEXT NOT NULL,
                status TEXT DEFAULT 'P',
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(worker_id, date)
            )
        """)
        conn.commit()
        
        # Seed if empty
        cur.execute("SELECT COUNT(*) FROM workers WHERE active=1")
        if cur.fetchone()[0] == 0:
            cur.executemany("INSERT INTO workers (name, phone, role, monthly_salary, active) VALUES (?, ?, ?, ?, ?)", [
                ("A1 (Senior Mechanic)", "9344885449", "Senior Mechanic", 18000.0, 1),
                ("A2 (EV Technician)", "8428544972", "EV Technician", 15000.0, 1),
                ("Kumar (Battery Specialist)", "9876543210", "Battery Specialist", 16000.0, 1),
                ("Suresh (Helper)", "9123456780", "Helper", 12000.0, 1),
            ])
            conn.commit()
        
        # 1. DAILY ATTENDANCE
        if att_subview == "📅 Daily Attendance Register":
            st.markdown("### 📋 Daily Attendance Sheet (S.No | Name | A/P | Date and Day)")
            col_d1, col_d2, col_d3 = st.columns([2, 1, 1])
            with col_d1:
                att_date = st.date_input("Select Date", datetime.date.today(), key="st_att_date")
                day_name = att_date.strftime("%A")
                st.caption(f"📅 **Date & Day:** `{att_date}` ({day_name})")
            
            with col_d2:
                mark_all_p = st.button("🟢 Mark All Present (P)")
            with col_d3:
                mark_all_a = st.button("🔴 Mark All Absent (A)")
            
            cur.execute("SELECT id, name, role, phone, monthly_salary FROM workers WHERE active=1 ORDER BY id")
            workers_list = cur.fetchall()
            
            # Fetch existing records for this date
            cur.execute("SELECT worker_id, status, notes FROM attendance WHERE date=?", (str(att_date),))
            existing_records = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
            
            att_entries = []
            st.divider()
            
            for idx, w in enumerate(workers_list, start=1):
                w_id, w_name, w_role, w_phone, w_sal = w
                prev_status, prev_notes = existing_records.get(w_id, ("P", ""))
                if mark_all_p:
                    prev_status = "P"
                elif mark_all_a:
                    prev_status = "A"
                
                c_sno, c_name, c_status, c_notes = st.columns([0.5, 2.5, 2, 2])
                with c_sno:
                    st.write(f"**{idx}**")
                with c_name:
                    st.write(f"**{w_name}**  \n<span style='color: #718096; font-size: 12px;'>{w_role} | ₹{w_sal:,.0f}/mo</span>", unsafe_allow_html=True)
                with c_status:
                    status_choice = st.radio(
                        f"Status for {w_name}",
                        ["P (Present)", "A (Absent)", "HD (Half Day)"],
                        index=0 if prev_status == "P" else (1 if prev_status == "A" else 2),
                        key=f"st_status_{w_id}_{att_date}",
                        horizontal=True,
                        label_visibility="collapsed"
                    )
                    clean_st = "P" if "Present" in status_choice else ("A" if "Absent" in status_choice else "HD")
                with c_notes:
                    note_val = st.text_input(f"Notes for {w_name}", value=prev_notes, key=f"st_notes_{w_id}_{att_date}", placeholder="Remarks (Leave, Sick...)", label_visibility="collapsed")
                
                att_entries.append((w_id, clean_st, note_val))
                st.write("---")
            
            if st.button("💾 SAVE ATTENDANCE", type="primary", use_container_width=True):
                for w_id, status_val, notes_val in att_entries:
                    cur.execute("""
                        INSERT INTO attendance (worker_id, date, day_name, status, notes)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(worker_id, date) DO UPDATE SET
                            day_name=excluded.day_name,
                            status=excluded.status,
                            notes=excluded.notes
                    """, (w_id, str(att_date), day_name, status_val, notes_val))
                conn.commit()
                st.success(f"✅ Attendance for {att_date} ({day_name}) saved successfully!")
                st.rerun()

        # 2. MONTH-END SALARY CALCULATION
        elif att_subview == "💰 Month-End Salary Calculation":
            st.markdown("### 💰 Month-End Overall Salary Calculation")
            col_m1, col_m2 = st.columns([1, 1])
            with col_m1:
                calc_month = st.selectbox("Select Month", list(range(1, 13)), index=datetime.date.today().month - 1, format_func=lambda m: calendar.month_name[m])
            with col_m2:
                calc_year = st.selectbox("Select Year", [2025, 2026, 2027], index=1)
            
            days_in_month = calendar.monthrange(calc_year, calc_month)[1]
            start_date = f"{calc_year}-{str(calc_month).zfill(2)}-01"
            end_date = f"{calc_year}-{str(calc_month).zfill(2)}-{str(days_in_month).zfill(2)}"
            
            cur.execute("SELECT id, name, role, phone, monthly_salary FROM workers WHERE active=1 ORDER BY id")
            workers_list = cur.fetchall()
            
            salary_rows = []
            total_gross = 0.0
            total_deductions = 0.0
            total_net = 0.0
            
            for idx, w in enumerate(workers_list, start=1):
                w_id, w_name, w_role, w_phone, w_sal = w
                
                cur.execute("""
                    SELECT status, COUNT(*) FROM attendance
                    WHERE worker_id=? AND date>=? AND date<=?
                    GROUP BY status
                """, (w_id, start_date, end_date))
                counts = dict(cur.fetchall())
                
                p_cnt = counts.get("P", 0) + 0.5 * counts.get("HD", 0)
                a_cnt = counts.get("A", 0) + 0.5 * counts.get("HD", 0)
                
                # 1 Paid Leave Allowed per Month rule:
                if a_cnt <= 1.0:
                    paid_leaves_used = a_cnt
                    deductible_days = 0.0
                else:
                    paid_leaves_used = 1.0
                    deductible_days = a_cnt - 1.0
                
                daily_wage = round(w_sal / days_in_month, 2)
                deduction_amt = round(deductible_days * daily_wage, 2)
                net_salary = max(0.0, round(w_sal - deduction_amt, 2))
                
                total_gross += w_sal
                total_deductions += deduction_amt
                total_net += net_salary
                
                if a_cnt == 0:
                    tag = "Full Salary (0 Leaves)"
                elif a_cnt <= 1:
                    tag = "Full Salary (1 Paid Leave Applied)"
                elif a_cnt == 2:
                    tag = "1 Day Reduced (2 Leaves)"
                else:
                    tag = f"{int(deductible_days)} Days Reduced ({int(a_cnt)} Leaves)"
                
                salary_rows.append({
                    "S.No": idx,
                    "Worker Name": w_name,
                    "Role": w_role,
                    "Base Salary (₹)": w_sal,
                    "Present": p_cnt,
                    "Leaves": a_cnt,
                    "Paid Leave Used": f"{paid_leaves_used} / 1",
                    "Deductible Days": deductible_days,
                    "Daily Rate (₹)": daily_wage,
                    "Deduction (₹)": deduction_amt,
                    "Net Salary (₹)": net_salary,
                    "Status": tag,
                    "Phone": w_phone
                })
            
            # Metrics
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Active Workers", len(workers_list))
            m_col2.metric("Gross Payroll", f"₹{total_gross:,.2f}")
            m_col3.metric("Leave Deductions", f"₹{total_deductions:,.2f}")
            m_col4.metric("Net Payable Payroll", f"₹{total_net:,.2f}")
            
            st.dataframe(pd.DataFrame(salary_rows).drop(columns=["Phone"]), use_container_width=True)
            
            # Download CSV
            csv_buf = io.StringIO()
            pd.DataFrame(salary_rows).to_csv(csv_buf, index=False)
            st.download_button(
                label="📥 Download Salary Register (CSV)",
                data=csv_buf.getvalue(),
                file_name=f"SDM_Payroll_{calendar.month_name[calc_month]}_{calc_year}.csv",
                mime="text/csv"
            )
            
            # WhatsApp Pay Slip Share
            st.markdown("#### 💬 Share Salary Slip via WhatsApp")
            selected_worker_name = st.selectbox("Select Worker to Share Slip", [r["Worker Name"] for r in salary_rows])
            if selected_worker_name:
                w_row = next(r for r in salary_rows if r["Worker Name"] == selected_worker_name)
                wa_msg = f"*SRI DHANAM MOTORS - SALARY SLIP*\n" \
                         f"------------------------------------\n" \
                         f"👤 Worker: {w_row['Worker Name']}\n" \
                         f"📅 Month: {calendar.month_name[calc_month]} {calc_year}\n" \
                         f"💼 Base Salary: ₹{w_row['Base Salary (₹)']:,.2f}\n" \
                         f"🟢 Present Days: {w_row['Present']}\n" \
                         f"🔴 Leave Days: {w_row['Leaves']}\n" \
                         f"✨ Paid Leave Applied: {w_row['Paid Leave Used']} Day\n" \
                         f"📉 Leave Deductions: ₹{w_row['Deduction (₹)']:,.2f}\n" \
                         f"------------------------------------\n" \
                         f"💰 *NET PAYABLE SALARY: ₹{w_row['Net Salary (₹)']:,.2f}*\n" \
                         f"------------------------------------\n" \
                         f"Thank you for your dedicated service at Sri Dhanam Motors!"
                
                clean_phone = "".join(filter(str.isdigit, str(w_row["Phone"])))
                if len(clean_phone) == 10:
                    clean_phone = "91" + clean_phone
                
                wa_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}"
                st.markdown(f'<a href="{wa_url}" target="_blank" style="display: inline-block; padding: 10px 18px; background: #25D366; color: white; border-radius: 6px; text-decoration: none; font-weight: bold;">💬 Open WhatsApp & Send Pay Slip</a>', unsafe_allow_html=True)

        # 3. MANAGE WORKERS
        elif att_subview == "👥 Manage Workers":
            st.markdown("### 👥 Manage Shop Workers")
            with st.expander("➕ Add New Worker"):
                with st.form("new_worker_form"):
                    w_name = st.text_input("Worker Name (e.g. A1, Ramesh)")
                    w_phone = st.text_input("Mobile Number (10 digits)")
                    w_role = st.selectbox("Role", ["Senior Mechanic", "EV Technician", "Battery Specialist", "Service Assistant", "Helper", "Sales Executive"])
                    w_salary = st.number_input("Monthly Base Salary (₹)", value=15000.0, step=500.0)
                    
                    if st.form_submit_button("Add Worker"):
                        if w_name.strip():
                            cur.execute("INSERT INTO workers (name, phone, role, monthly_salary, active) VALUES (?, ?, ?, ?, 1)", (w_name.strip(), w_phone.strip(), w_role, float(w_salary)))
                            conn.commit()
                            st.success(f"Worker '{w_name}' added successfully!")
                            st.rerun()
                        else:
                            st.error("Please enter a worker name.")
            
            cur.execute("SELECT id, name, phone, role, monthly_salary, active FROM workers ORDER BY id")
            all_w = cur.fetchall()
            df_w = pd.DataFrame(all_w, columns=["ID", "Name", "Phone", "Role", "Monthly Salary (₹)", "Active"])
            st.dataframe(df_w, use_container_width=True)
        
        conn.close()

# -------------------- TAB 7: DAILY EXPENSES --------------------
with tab7:
    st.subheader("💸 Daily Expenses Tracker (தினசரி செலவுகள்)")
    st.caption("Record and monitor shop expenses. Standard date is loaded automatically. Bill number is optional.")

    conn_exp = get_sqlite()
    if conn_exp is None:
        st.error("Database file not found at " + db_file)
    else:
        cur_exp = conn_exp.cursor()
        cur_exp.execute("""
            CREATE TABLE IF NOT EXISTS daily_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                bill_no TEXT DEFAULT '',
                product_name TEXT DEFAULT '',
                price REAL DEFAULT 0.0,
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn_exp.commit()

        # Input Card / Form
        st.markdown("### ➕ Add Daily Expense")
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            exp_date = st.date_input("Date", datetime.date.today(), key="st_exp_date")
            st.caption(f"📅 Auto-loaded: `{exp_date}`")
        with col_e2:
            exp_bill_no = st.text_input("Bill Number (Optional)", key="st_exp_bill_no", placeholder="e.g. B-104 or leave blank")
            st.caption("ℹ️ Bill number is optional")
        with col_e3:
            exp_product = st.text_input("Product / Description", key="st_exp_prod", placeholder="e.g. Tea & Snacks, Petrol, Cleaning")

        col_e4, col_e5 = st.columns([1, 2])
        with col_e4:
            exp_price = st.number_input("Price / Amount (₹)", min_value=0.0, step=10.0, value=0.0, key="st_exp_price")
        with col_e5:
            exp_notes = st.text_input("Notes / Remarks (Optional)", key="st_exp_notes", placeholder="e.g. Paid cash to shop helper")

        if st.button("💾 SAVE EXPENSE", type="primary", key="btn_save_expense"):
            clean_prod = exp_product.strip()
            clean_bill = exp_bill_no.strip()
            # Non-compulsory rule: bill number is optional; save if product or price or bill is entered
            if not clean_prod and exp_price <= 0 and not clean_bill:
                st.warning("⚠️ Please enter at least a product description or expense amount.")
            else:
                cur_exp.execute("""
                    INSERT INTO daily_expenses (date, bill_no, product_name, price, notes)
                    VALUES (?, ?, ?, ?, ?)
                """, (str(exp_date), clean_bill, clean_prod, float(exp_price), exp_notes.strip()))
                conn_exp.commit()
                st.success(f"✅ Expense of ₹{exp_price:,.2f} recorded successfully for {exp_date}!")
                st.rerun()

        st.divider()

        # Summary Metrics
        today_str = str(datetime.date.today())
        month_prefix = datetime.date.today().strftime("%Y-%m")

        cur_exp.execute("SELECT COALESCE(SUM(price), 0.0), COUNT(*) FROM daily_expenses WHERE date=?", (today_str,))
        today_sum, today_count = cur_exp.fetchone()

        cur_exp.execute("SELECT COALESCE(SUM(price), 0.0) FROM daily_expenses WHERE strftime('%Y-%m', date)=?", (month_prefix,))
        month_sum = cur_exp.fetchone()[0]

        cur_exp.execute("SELECT COALESCE(SUM(price), 0.0), COUNT(*) FROM daily_expenses")
        all_sum, all_count = cur_exp.fetchone()

        m_e1, m_e2, m_e3 = st.columns(3)
        m_e1.metric("Today's Expenses", f"₹{today_sum:,.2f}", f"{today_count} entries")
        m_e2.metric("This Month's Total", f"₹{month_sum:,.2f}")
        m_e3.metric("All-Time Total", f"₹{all_sum:,.2f}", f"{all_count} total")

        st.markdown("### 📋 Daily Expenses History")
        cur_exp.execute("SELECT id, date, bill_no, product_name, price, notes, created_at FROM daily_expenses ORDER BY date DESC, id DESC")
        exp_rows = cur_exp.fetchall()

        if exp_rows:
            exp_df = pd.DataFrame(exp_rows, columns=["ID", "Date", "Bill No", "Product / Description", "Price (₹)", "Notes", "Recorded At"])
            st.dataframe(exp_df, use_container_width=True)

            csv_exp_buf = io.StringIO()
            exp_df.to_csv(csv_exp_buf, index=False)
            col_d1, col_d2 = st.columns([1, 1])
            with col_d1:
                st.download_button(
                    label="📥 Download Expenses CSV",
                    data=csv_exp_buf.getvalue(),
                    file_name=f"SDM_Daily_Expenses_{today_str}.csv",
                    mime="text/csv",
                    key="dl_exp_csv"
                )
            with col_d2:
                with st.expander("🗑️ Delete an Expense Record"):
                    del_exp_id = st.selectbox("Select Expense ID to delete", [r[0] for r in exp_rows], format_func=lambda x: f"ID #{x} - {next((r[3] or r[2]) for r in exp_rows if r[0]==x)} (₹{next(r[4] for r in exp_rows if r[0]==x)})")
                    if st.button("Delete Selected Expense", type="secondary", key="btn_del_exp"):
                        cur_exp.execute("DELETE FROM daily_expenses WHERE id=?", (del_exp_id,))
                        conn_exp.commit()
                        st.success(f"Expense #{del_exp_id} deleted.")
                        st.rerun()
        else:
            st.info("No daily expenses recorded yet. Add your first expense above.")

        conn_exp.close()

# -------------------- TAB 8: INWARD / PURCHASE BILLS --------------------
with tab8:
    st.subheader("📥 Inward Purchases & Bulk GST Bills (கடை பர்ச்சேஸ் பில்)")
    st.caption("Record supplier bulk purchase bills, date received, price, and total quantity.")

    conn_pur = get_sqlite()
    if conn_pur is None:
        st.error("Database file not found at " + db_file)
    else:
        cur_pur = conn_pur.cursor()
        cur_pur.execute("""
            CREATE TABLE IF NOT EXISTS purchase_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT NOT NULL,
                received_date DATE NOT NULL,
                price REAL DEFAULT 0.0,
                total_qty INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn_pur.commit()

        # Input Card / Form
        st.markdown("### ➕ Record Inward Purchase Bill")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pur_inv_no = st.text_input("Invoice / Bill Number *", key="st_pur_inv_no", placeholder="e.g. GST-PUR-2026-089")
            pur_date = st.date_input("Date Received", datetime.date.today(), key="st_pur_date")
            st.caption(f"📅 Received date auto-loaded: `{pur_date}`")
        with col_p2:
            pur_price = st.number_input("Price / Bill Amount (₹) *", min_value=0.0, step=100.0, value=0.0, key="st_pur_price")
            pur_qty = st.number_input("Total Number of Quantity *", min_value=0, step=1, value=1, key="st_pur_qty")

        pur_notes = st.text_input("Notes / Supplier Details (Optional)", key="st_pur_notes", placeholder="e.g. Bulk motors and batteries from OEM supplier")

        if st.button("💾 SAVE PURCHASE BILL", type="primary", key="btn_save_purchase"):
            clean_inv = pur_inv_no.strip()
            if not clean_inv:
                st.error("⚠️ Please enter the Invoice / Bill Number.")
            else:
                cur_pur.execute("""
                    INSERT INTO purchase_invoices (invoice_no, received_date, price, total_qty, notes)
                    VALUES (?, ?, ?, ?, ?)
                """, (clean_inv, str(pur_date), float(pur_price), int(pur_qty), pur_notes.strip()))
                conn_pur.commit()
                st.success(f"✅ Purchase Bill '{clean_inv}' for ₹{pur_price:,.2f} ({pur_qty} units) saved successfully!")
                st.rerun()

        st.divider()

        # Summary Metrics
        cur_pur.execute("SELECT COALESCE(SUM(price), 0.0), COALESCE(SUM(total_qty), 0), COUNT(*) FROM purchase_invoices")
        tot_pur_amt, tot_pur_qty, tot_pur_cnt = cur_pur.fetchone()

        month_prefix = datetime.date.today().strftime("%Y-%m")
        cur_pur.execute("SELECT COALESCE(SUM(price), 0.0), COALESCE(SUM(total_qty), 0) FROM purchase_invoices WHERE strftime('%Y-%m', received_date)=?", (month_prefix,))
        m_pur_amt, m_pur_qty = cur_pur.fetchone()

        mp_1, mp_2, mp_3 = st.columns(3)
        mp_1.metric("Total Inward Spend", f"₹{tot_pur_amt:,.2f}", f"{tot_pur_cnt} bills")
        mp_2.metric("Total Quantity Received", f"{tot_pur_qty:,} Units")
        mp_3.metric("This Month's Inward", f"₹{m_pur_amt:,.2f}", f"{m_pur_qty} units")

        st.markdown("### 📋 Inward Purchase Register")
        cur_pur.execute("SELECT id, invoice_no, received_date, total_qty, price, notes, created_at FROM purchase_invoices ORDER BY received_date DESC, id DESC")
        pur_rows = cur_pur.fetchall()

        if pur_rows:
            pur_df = pd.DataFrame(pur_rows, columns=["ID", "Invoice / Bill No", "Date Received", "Total Quantity", "Price (₹)", "Notes / Supplier", "Recorded At"])
            st.dataframe(pur_df, use_container_width=True)

            csv_pur_buf = io.StringIO()
            pur_df.to_csv(csv_pur_buf, index=False)
            col_pd1, col_pd2 = st.columns([1, 1])
            with col_pd1:
                st.download_button(
                    label="📥 Download Purchases CSV",
                    data=csv_pur_buf.getvalue(),
                    file_name=f"SDM_Inward_Purchases_{datetime.date.today()}.csv",
                    mime="text/csv",
                    key="dl_pur_csv"
                )
            with col_pd2:
                with st.expander("🗑️ Delete a Purchase Record"):
                    del_pur_id = st.selectbox("Select Purchase ID to delete", [r[0] for r in pur_rows], format_func=lambda x: f"ID #{x} - {next(r[1] for r in pur_rows if r[0]==x)} (₹{next(r[4] for r in pur_rows if r[0]==x)})")
                    if st.button("Delete Selected Purchase", type="secondary", key="btn_del_pur"):
                        cur_pur.execute("DELETE FROM purchase_invoices WHERE id=?", (del_pur_id,))
                        conn_pur.commit()
                        st.success(f"Purchase Bill #{del_pur_id} deleted.")
                        st.rerun()
        else:
            st.info("No inward purchase bills recorded yet. Add your first bulk bill above.")

        conn_pur.close()
