import streamlit as st
import pandas as pd
from io import BytesIO
import unicodedata
from fpdf import FPDF
import requests
import os

# Ρυθμίσεις σελίδας
st.set_page_config(page_title="Σύγκριση Τιμών Φαρμάκων", page_icon="💊", layout="wide")

st.title("💊 Σύγκριση: Παλιά ΧΤ vs Προτεινόμενη ΧΤ")
st.markdown("Αυτόματη σύγκριση, υπολογισμός διαφορών και εξαγωγή σε **Excel & PDF**.")

# --- Βοηθητικές Συναρτήσεις ---

def normalize_text(text):
    """Καθαρίζει τόνους και κεφαλαία"""
    if not isinstance(text, str): return str(text)
    text = text.upper()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def load_data(file):
    if file:
        try:
            return pd.read_excel(file)
        except Exception as e:
            st.error(f"Σφάλμα αρχείου: {e}")
    return None

def find_exact_column(columns, target_keywords):
    """Ψάχνει στήλη που περιέχει τις λέξεις κλειδιά"""
    for col in columns:
        norm_col = normalize_text(col)
        if all(normalize_text(k) in norm_col for k in target_keywords):
            return col
    return None

# --- Συνάρτηση για PDF ---
def create_pdf(df):
    # Έλεγχος/Λήψη Ελληνικής Γραμματοσειράς (Απαραίτητο για το PDF)
    font_path = "Roboto-Regular.ttf"
    if not os.path.exists(font_path):
        url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf"
        r = requests.get(url, allow_redirects=True)
        with open(font_path, 'wb') as f:
            f.write(r.content)

    class PDF(FPDF):
        def header(self):
            self.set_font('Roboto', 'B', 12)
            self.cell(0, 10, 'Λίστα Διαφορών Τιμών Φαρμάκων', 0, 1, 'C')
            self.ln(5)
            
            # Επικεφαλίδες Πίνακα
            self.set_font('Roboto', 'B', 8)
            self.set_fill_color(200, 220, 255)
            
            # Ορισμός πλάτους στηλών (Σύνολο ~275 για A4 Landscape)
            # Barcode | Ονομασία | ΠΧΤ | ΝΧΤ | δ% | Διαφορά
            self.cell(30, 8, 'Barcode', 1, 0, 'C', 1)
            self.cell(110, 8, 'Ονομασία', 1, 0, 'C', 1)
            self.cell(25, 8, 'ΠΧΤ', 1, 0, 'C', 1)
            self.cell(25, 8, 'ΝΧΤ', 1, 0, 'C', 1)
            self.cell(20, 8, 'δ%', 1, 0, 'C', 1)
            self.cell(25, 8, 'Διαφορά', 1, 1, 'C', 1)

    # Δημιουργία PDF σε Landscape (L)
    pdf = PDF('L', 'mm', 'A4')
    pdf.add_font('Roboto', '', font_path, uni=True)
    pdf.add_font('Roboto', 'B', font_path, uni=True)
    pdf.add_page()
    pdf.set_font('Roboto', '', 8)

    # Γέμισμα δεδομένων
    for index, row in df.iterrows():
        # Προετοιμασία τιμών
        barcode = str(row['Barcode'])
        name = str(row['Ονομασία'])[:55] # Κόψιμο ονόματος αν είναι τεράστιο για να χωράει
        pxt = f"{row['ΠΧΤ']:.2f}€"
        nxt = f"{row['ΝΧΤ']:.2f}€"
        diff_pct = f"{row['δ%']:+.2f}%"
        diff_val = f"{row['Διαφορά']:+.2f}€"

        pdf.cell(30, 7, barcode, 1, 0, 'C')
        pdf.cell(110, 7, name, 1, 0, 'C') # Ονομασία κεντραρισμένη
        pdf.cell(25, 7, pxt, 1, 0, 'C')
        pdf.cell(25, 7, nxt, 1, 0, 'C')
        pdf.cell(20, 7, diff_pct, 1, 0, 'C')
        pdf.cell(25, 7, diff_val, 1, 1, 'C')

    return pdf.output(dest='S').encode('latin-1', 'ignore') 
    # Σημείωση: Το .output() επιστρέφει string στο fpdf1.7, το encode χρειάζεται για bytes. 
    # Αν χρησιμοποιηθεί fpdf2 είναι λίγο διαφορετικό, αλλά αυτό δουλεύει για standard fpdf.

# --- Upload Files ---
st.write("---")
c1, c2 = st.columns(2)
old_file = c1.file_uploader("📂 ΠΑΛΙΟ Δελτίο", type=['xlsx', 'xls'])
new_file = c2.file_uploader("📂 ΝΕΟ Δελτίο", type=['xlsx', 'xls'])

if old_file and new_file:
    df_old = load_data(old_file)
    df_new = load_data(new_file)

    if df_old is not None and df_new is not None:
        
        # --- ΑΝΑΓΝΩΡΙΣΗ ΣΤΗΛΩΝ ---
        col_barcode_old = find_exact_column(df_old.columns, ['BARCODE'])
        col_barcode_new = find_exact_column(df_new.columns, ['BARCODE'])
        col_name = find_exact_column(df_new.columns, ['ΠΡΟΙΟΝ'])
        col_price_old = find_exact_column(df_old.columns, ['ΧΟΝΔΡΙΚΗ', 'ΤΙΜΗ']) 
        col_price_new = find_exact_column(df_new.columns, ['ΠΡΟΤΕΙΝΟΜΕΝΗ', 'ΧΟΝΔΡΙΚΗ'])

        if not col_barcode_old or not col_barcode_new or not col_price_old or not col_price_new:
            st.error("⚠️ Δεν βρέθηκαν οι στήλες! Βεβαιωθείτε ότι υπάρχουν: Barcode, Χονδρική Τιμή, Προτεινόμενη Χονδρική Τιμή.")
        else:
            st.success("✅ Τα αρχεία διαβάστηκαν σωστά.")

            # --- ΕΠΕΞΕΡΓΑΣΙΑ ---
            d1 = df_old[[col_barcode_old, col_price_old]].copy()
            d1.columns = ['Barcode', 'Old_XT']
            
            d2 = df_new[[col_barcode_new, col_name, col_price_new]].copy()
            d2.columns = ['Barcode', 'Name', 'New_XT']

            for df_temp in [d1, d2]:
                t_col = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
                if df_temp[t_col].dtype == object:
                    df_temp[t_col] = df_temp[t_col].astype(str).str.replace(',', '.', regex=False)
                    df_temp[t_col] = pd.to_numeric(df_temp[t_col], errors='coerce')
                df_temp[t_col] = df_temp[t_col].fillna(0)
                df_temp['Barcode'] = df_temp['Barcode'].astype(str).str.strip().str.replace('.0', '', regex=False)

            merged = pd.merge(d2, d1, on='Barcode', how='left')

            # --- ΥΠΟΛΟΓΙΣΜΟΙ ---
            # Διαφορά (Νέο - Παλιό)
            merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
            
            # Ποσοστό: (Διαφορά / Παλιά Τιμή) * 100
            merged['Diff_Pct'] = merged.apply(
                lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
            )

            # Τελικός Πίνακας
            final = merged[['Barcode', 'Name', 'Old_XT', 'New_XT', 'Diff_Pct', 'Diff_Val']].copy()
            final.columns = ['Barcode', 'Ονομασία', 'ΠΧΤ', 'ΝΧΤ', 'δ%', 'Διαφορά']
            
            # Στρογγυλοποίηση για εμφάνιση
            final['ΠΧΤ'] = final['ΠΧΤ'].round(2)
            final['ΝΧΤ'] = final['ΝΧΤ'].round(2)
            final['δ%'] = final['δ%'].round(2)
            final['Διαφορά'] = final['Διαφορά'].round(2)

            # Φιλτράρισμα μόνο αλλαγών για το Preview και το PDF
            changes_only = final[final['Διαφορά'] != 0].sort_values(by='Διαφορά', ascending=False)

            # --- ΠΡΟΒΟΛΗ ---
            st.divider()
            st.subheader(f"📋 Αλλαγές Τιμών ({len(changes_only)})")
            
            # Styling για κεντράρισμα στο Streamlit preview
            st.dataframe(
                changes_only.head(50).style.format({
                    'ΠΧΤ': '{:.2f}€',
                    'ΝΧΤ': '{:.2f}€',
                    'δ%': '{:+.2f}%',
                    'Διαφορά': '{:+.2f}€'
                }).set_properties(**{'text-align': 'center'}) # Κεντράρισμα στο Preview
            )

            # --- EXPORT BUTTONS ---
            st.write("---")
            st.subheader("📥 Λήψη Αρχείων")
            
            col_d1, col_d2 = st.columns(2)

            # 1. EXCEL DOWNLOAD
            buffer_excel = BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='xlsxwriter') as writer:
                # Εξάγουμε ΟΛΑ τα δεδομένα ή μόνο τις αλλαγές; Συνήθως όλα.
                # Αν θες μόνο αλλαγές, βάλε changes_only αντί για final
                final.to_excel(writer, index=False, sheet_name='PriceChanges')
                wb = writer.book
                ws = writer.sheets['PriceChanges']
                
                # Ορισμός στυλ για ΚΕΝΤΡΑΡΙΣΜΑ (Center)
                center_format = wb.add_format({'align': 'center', 'valign': 'vcenter'})
                
                fmt_eur = wb.add_format({'num_format': '#,##0.00€', 'align': 'center', 'valign': 'vcenter'})
                fmt_diff_eur = wb.add_format({'num_format': '+#,##0.00€;-#,##0.00€;0.00€', 'align': 'center', 'valign': 'vcenter', 'bold': True})
                fmt_diff_pct = wb.add_format({'num_format': '+0.00%;-0.00%;0.00%', 'align': 'center', 'valign': 'vcenter'})
                
                # Εφαρμογή πλάτους και format
                ws.set_column('A:A', 16, center_format) # Barcode
                ws.set_column('B:B', 50, center_format) # Name
                ws.set_column('C:D', 12, fmt_eur)
                ws.set_column('E:E', 10, fmt_diff_pct)
                ws.set_column('F:F', 12, fmt_diff_eur)

                # Χρώματα για αυξομειώσεις
                ws.conditional_format('F2:F1048576', {'type': 'cell', 'criteria': '>', 'value': 0, 'format': wb.add_format({'font_color': '#9C0006', 'bg_color': '#FFC7CE', 'align': 'center'})})
                ws.conditional_format('F2:F1048576', {'type': 'cell', 'criteria': '<', 'value': 0, 'format': wb.add_format({'font_color': '#006100', 'bg_color': '#C6EFCE', 'align': 'center'})})

            with col_d1:
                st.download_button(
                    label="📄 Λήψη EXCEL",
                    data=buffer_excel.getvalue(),
                    file_name="pharmacy_prices.xlsx",
                    mime="application/vnd.ms-excel",
                    type="primary"
                )

            # 2. PDF DOWNLOAD
            # Για το PDF εξάγουμε μόνο τις αλλαγές για να μην βγει 1000 σελίδες, εκτός αν είναι άδειο
            pdf_data = changes_only if not changes_only.empty else final.head(100)
            
            # Δημιουργία PDF Bytes
            try:
                pdf_bytes = create_pdf(pdf_data)
                with col_d2:
                    st.download_button(
                        label="📕 Λήψη PDF (Αλλαγές)",
                        data=pdf_bytes,
                        file_name="pharmacy_prices.pdf",
                        mime="application/pdf"
                    )
            except Exception as e:
                st.error(f"Σφάλμα κατά τη δημιουργία PDF: {e}")
