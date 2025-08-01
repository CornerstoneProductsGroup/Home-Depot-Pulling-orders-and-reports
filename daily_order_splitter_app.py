
import streamlit as st
import os
import pandas as pd
import zipfile
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime

today_fmt = datetime.now().strftime("%-m-%-d-%Y")
base_output_dir = f"daily_output/{today_fmt}"
log_dir = "logs"
os.makedirs(base_output_dir, exist_ok=True)
os.makedirs(log_dir, exist_ok=True)

summary_records = []
error_log = []
summary_log_path = os.path.join(log_dir, "sent_orders_log.csv")
error_log_path = os.path.join(log_dir, "error_log.txt")

def log_error(msg):
    error_log.append(f"{datetime.now().isoformat()} - {msg}")

def load_home_depot_mapping(file):
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()
    sku_col = [col for col in df.columns if 'sku' in col.lower()][0]
    vendor_col = [col for col in df.columns if 'vendor' in col.lower()][0]
    email_cols = [col for col in df.columns if 'email' in col.lower()]
    email_col = email_cols[0] if email_cols else None

    mapping = {}
    for _, row in df.iterrows():
        sku = str(row[sku_col]).strip()
        vendor = str(row[vendor_col]).strip()
        email = str(row[email_col]).strip() if email_col and not pd.isna(row[email_col]) else ''
        mapping[sku] = {'vendor': vendor, 'email': email}
    return mapping

def split_by_vendor(pdf_file, sku_mapping):
    reader = PdfReader(pdf_file)
    result = {}
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        matched = False
        for sku, data in sku_mapping.items():
            if sku in text:
                vendor = data['vendor']
                if vendor not in result:
                    result[vendor] = {'writer': PdfWriter(), 'count': 0}
                result[vendor]['writer'].add_page(page)
                result[vendor]['count'] += 1
                matched = True
                break
        if not matched:
            log_error(f"Page {i+1}: No matching Home Depot SKU.")
    return result

def create_zip_files(page_map):
    store_dir = os.path.join(base_output_dir, "Depot")
    os.makedirs(store_dir, exist_ok=True)
    zip_path = os.path.join(base_output_dir, f"Depot {today_fmt}.zip")
    zf = zipfile.ZipFile(zip_path, 'w')

    for vendor, data in page_map.items():
        filename = f"Depot {today_fmt} order page 1 {vendor}.pdf"
        pdf_path = os.path.join(store_dir, filename)
        with open(pdf_path, "wb") as f:
            data['writer'].write(f)
        zf.write(pdf_path, arcname=filename)
        summary_records.append({
            'Store': 'Depot',
            'Vendor': vendor,
            'Pages': data['count'],
            'PDF': filename,
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Status': 'Prepared'
        })

    zf.close()

def update_logs():
    if summary_records:
        df = pd.DataFrame(summary_records)
        log_file = os.path.join(base_output_dir, f"Depot {today_fmt} summary report.csv")
        df.to_csv(log_file, index=False)
        if os.path.exists(summary_log_path):
            df_existing = pd.read_csv(summary_log_path)
            df_combined = pd.concat([df_existing, df], ignore_index=True)
        else:
            df_combined = df
        df_combined.to_csv(summary_log_path, index=False)
    if error_log:
        with open(error_log_path, "a") as f:
            for e in error_log:
                f.write(e + "\n")

st.title("🏗️ Home Depot Order Splitter (Vendor Separation Only)")

sku_file = st.file_uploader("Upload Home Depot SKU to Vendor Sheet", type=["xlsx"])
pdf_file = st.file_uploader("Upload Home Depot Orders PDF", type=["pdf"])

if sku_file and pdf_file:
    st.success("Files uploaded. Ready to split.")
    if st.button("🚀 Process Home Depot Orders"):
        sku_mapping = load_home_depot_mapping(sku_file)
        page_map = split_by_vendor(pdf_file, sku_mapping)
        if not page_map:
            st.error("No matched Home Depot pages found.")
        else:
            create_zip_files(page_map)
            update_logs()
            st.success("✅ Orders split by vendor.")
            st.metric("Total Vendors", len(page_map))
            st.metric("Total Pages", sum(p['count'] for p in page_map.values()))
            st.metric("Errors Logged", len(error_log))

            if summary_records:
                st.subheader("📊 Summary Report")
                st.dataframe(pd.DataFrame(summary_records))

            zip_filename = f"Depot {today_fmt}.zip"
            zip_path = os.path.join(base_output_dir, zip_filename)
            csv_filename = f"Depot {today_fmt} summary report.csv"
            csv_path = os.path.join(base_output_dir, csv_filename)

            if os.path.exists(zip_path):
                with open(zip_path, "rb") as f:
                    st.download_button("📦 Download ZIP File", f, file_name=zip_filename)

            if os.path.exists(csv_path):
                with open(csv_path, "rb") as f:
                    st.download_button("📊 Download Summary CSV", f, file_name=csv_filename)
else:
    st.info("Please upload both the Home Depot SKU sheet and the PDF file.")
