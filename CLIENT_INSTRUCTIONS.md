# Sri Dhanam Motors - Client Quick Start & User Guide

Welcome to the **Sri Dhanam Motors** Billing & Inventory Management System.

---

## 🚀 How to Start the Application

You do **not** need to type any terminal commands! Simply:

1. **Double-click** the file:
   ```text
   START_BILLING_APP.bat
   ```
   *(Or `run_billing_app.bat`)*

2. The application will start and **automatically open your web browser** to:
   👉 **http://127.0.0.1:8000**

3. **Keep the black console window open** while using the software. When you are done for the day, you can close the window or press `Ctrl + C`.

---

## 📱 How to Use on Mobile Phone or Second Counter (Wi-Fi)

You can use the billing software from any mobile phone or laptop connected to the shop's Wi-Fi network:

1. Open PowerShell or Command Prompt on the main PC and type:
   ```cmd
   ipconfig
   ```
2. Look for **IPv4 Address** (for example: `192.168.1.15`).
3. On your phone's browser, open:
   ```text
   http://192.168.1.15:8000
   ```
4. You can now create bills, check stock, and manage attendance directly from your phone!

---

## 💾 How to Back Up Your Data (One-Click)

To make sure your invoices and stock records are always safe:

1. **Double-click**:
   ```text
   BACKUP_DATABASE.bat
   ```
2. A timestamped copy of your database will be saved automatically inside the `backups/` folder (e.g., `sdm_backup_2026-10-24.db`).
3. You can copy this file to a USB drive or Google Drive periodically.

---

## 📋 Features Overview

| Feature | Description |
| :--- | :--- |
| **📊 Dashboard** | Daily, Weekly, and Monthly sales trends, GST collection, and low-stock alerts. |
| **🧾 Spare Bill** | Fast spare parts billing with Customer / Dealer pricing and GST calculation. |
| **🔧 Service Bill** | EV repair and service billing with customer details and printable receipts. |
| **🛵 Vehicle Bill** | EV Scooter & vehicle billing with JHEV Motors dealer branding and profit margin control. |
| **🔋 Battery QR** | Generate and print unique battery serials (`SDM0001`...) with QR codes and Code128 barcodes. |
| **📦 Product & Stock** | Manage parts catalog, instant stock add/reduce, Excel/CSV import and export. |
| **💸 Daily Expenses** | Track shop expenses (tea, cleaning, petty cash) with optional bill numbers. |
| **📥 Inward Purchases**| Record vendor bills and incoming stock shipments with GST. |
| **👷 Attendance & Salary** | Daily worker attendance register, leave policy calculation, and printable salary vouchers. |
| **🏷️ Printer Settings** | TVS-E LP 46 thermal barcode printer configuration and test print. |

---

## 🖨️ TVS-E LP 46 Thermal Barcode Printer Setup

1. Connect the TVS LP 46 printer via USB.
2. Install the Windows driver.
3. In the application, navigate to **🏷️ Printer Settings** from the top menu.
4. Select **TVS LP 46** from the detected printers list.
5. Choose your label size (default is **50 × 30 mm**).
6. Click **Test Print** to verify your setup.

---

## 📞 Support & Shop Metadata

- **Shop:** SRI DHANAM MOTORS
- **Tagline:** ⚡ SALES, SERVICES & SPARES (Authorized JHEV Motors Dealer)
- **Address:** Near RTO Office Mobirippatti, Harur (Tk), Dharmapuri (Dt) - 636903
- **Phones:** +91 9344885449, +91 8428544972
- **GSTIN:** Applied (A/F)
