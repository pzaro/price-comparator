import streamlit as st
import pandas as pd
from io import BytesIO
import unicodedata
from fpdf import FPDF
import requests
import os

# Ρυθμίσεις σελίδας
st.set_page_config(page_title="Price Change Analyzer", page_icon="📉", layout="wide")

st.title("📉 Έλεγχος Αλλαγών Τιμών Φαρμάκων")

# --- ΣΥΝΑΡΤΗΣΕΙΣ ---

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

def create_pdf_file(df):
    """Δημιουργεί PDF και επιστρέφει το path του αρχείου"""
    # 1. Λήψη Font (Roboto) αν δεν υπάρχει
    font_path = "Roboto-Regular.ttf"
    if not os.path.exists(font_path):
        try:
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf"
            r = requests.get(url, allow_redirects=True)
            with open(font_path, 'wb') as f:
                f.write(r.content)
        except:
            st.warning("Δεν βρέθηκε η γραμματοσειρά, το PDF ίσως δεν εμφανίσει σωστά τα Ελληνικά.")

    # 2. Ρύθμιση PDF
    pdf = FPDF('L', 'mm', 'A4') # Landscape
    pdf.add_page()
    
    # Προσθήκη γραμματοσειράς
    try:
        pdf.add_font('Roboto', '', font_path, uni=True)
        pdf.set_font('Roboto', '', 8)
    except:
        pdf.set_font('Arial', '', 8) # Fallback

    # Header
    pdf.set_font_size(14)
    pdf.cell(0, 10, f'Λίστα Αλλαγών Τιμών ({len(df)} είδη)', 0, 1, 'C')
    pdf.ln(5)

    # Table Header
    pdf.set_font_size(8)
    pdf.set_fill_color(220, 220, 220)
    
    # Barcode(30) | Name(120) | Old(25) | New(25) | Diff%(20) | DiffVal(25)
    pdf.cell(30, 8, 'Barcode', 1, 0, 'C', 1)
    pdf.cell(120, 8, 'Ονομασία', 1, 0, 'C', 1)
    pdf.cell(25, 8, 'ΠΧΤ', 1, 0, 'C', 1)
    pdf.cell(25, 8, 'ΝΧΤ', 1, 0, 'C', 1)
    pdf.cell(20, 8, 'δ%', 1, 0, 'C', 1)
    pdf.cell(25, 8, 'Διαφορά', 1, 1, 'C', 1)

    # Rows
    for _, row in df.iterrows():
        barcode = str(row['Barcode'])
        name = str(row['Ονομασία'])[:65] # Κόψιμο αν είναι πολύ μεγάλο
        pxt = f"{row['ΠΧΤ']:.2f}"
        nxt = f"{row['ΝΧΤ']:.2f}"
        dpct = f"{row['δ%']:+.1f}%"
        dval = f"{row['Διαφορά']:+.2f}"

        # Χρώμα για τη διαφορά (δεν υποστηρίζεται εύκολα cell-by-cell fill στο απλό fpdf χωρίς library hacks, 
        # οπότε αφήνουμε ασπρόμαυρο για ασφάλεια και ταχύτητα)
        
        pdf.cell(30, 6, barcode, 1, 0, 'C')
        pdf.cell(120, 6, name, 1, 0, 'L') # Name Left aligned καλύτερα
        pdf.cell(25, 6, pxt, 1, 0, 'C')
        pdf.cell(25, 6, nxt, 1, 0, 'C')
        pdf.cell(20, 6, dpct, 1, 0, 'C')
        pdf.cell(25, 6, dval, 1, 1, 'C')

    output_filename = "report_temp.pdf"
    pdf.output(output_filename)
    return output_filename

# --- ΚΥΡΙΩΣ ΠΡΟΓΡΑΜΜΑ ---

st.write("---")
c1, c2 = st.columns(2)
old_file = c1.file_uploader("📂 ΠΑΛΙΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'])
new_file = c2.file_uploader("📂 ΝΕΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'])

if old_file and new_file:
    # Load Data
    df_old = load_data(old_file)
    df_new = load_data(new_file)

    if df_old is not None and df_new is not None:
        
        # Identify Columns
        col_barcode_old = find_exact_column(df_old.columns, ['BARCODE'])
        col_barcode_new = find_exact_column(df_new.columns, ['BARCODE'])
        col_name = find_exact_column(df_new.columns, ['ΠΡΟΙΟΝ'])
        col_price_old = find_exact_column(df_old.columns, ['ΧΟΝΔΡΙΚΗ', 'ΤΙΜΗ']) 
        col_price_new = find_exact_column(df_new.columns, ['ΠΡΟΤΕΙΝΟΜΕΝΗ', 'ΧΟΝΔΡΙΚΗ'])

        if not (col_barcode_old and col_barcode_new and col_price_old and col_price_new):
            st.error("⚠️ Λείπουν στήλες! Ελέγξτε ότι υπάρχουν: Barcode, Χονδρική Τιμή, Προτεινόμενη Χονδρική Τιμή.")
        else:
            # Data Processing
            d1 = df_old[[col_barcode_old, col_price_old]].copy()
            d1.columns = ['Barcode', 'Old_XT']
            
            d2 = df_new[[col_barcode_new, col_name, col_price_new]].copy()
            d2.columns = ['Barcode', 'Name', 'New_XT']

            # Clean Numeric & Barcodes
            for df_temp in [d1, d2]:
                t_col = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
                if df_temp[t_col].dtype == object:
                    df_temp[t_col] = df_temp[t_col].astype(str).str.replace(',', '.', regex=False)
                    df_temp[t_col] = pd.to_numeric(df_temp[t_col], errors='coerce')
                df_temp[t_col] = df_temp[t_col].fillna(0)
                df_temp['Barcode'] = df_temp['Barcode'].astype(str).str.strip().str.replace('.0', '', regex=False)

            # Merge
            merged = pd.merge(d2, d1, on='Barcode', how='left')

            # Calc
            merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
            merged['Diff_Pct'] = merged.apply(
                lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
            )

            # Final Table Format
            final = merged[['Barcode', 'Name', 'Old_XT', 'New_XT', 'Diff_Pct', 'Diff_Val']].copy()
            final.columns = ['Barcode', 'Ονομασία', 'ΠΧΤ', 'ΝΧΤ', 'δ%', 'Διαφορά']
            
            # Rounding
            for c in ['ΠΧΤ', 'ΝΧΤ', 'δ%', 'Διαφορά']:
                final[c] = final[c].round(2)

            # --- ΦΙΛΤΡΟ: ΜΟΝΟ ΟΙ ΑΛΛΑΓΕΣ ---
            # Κρατάμε μόνο όσα έχουν διαφορά != 0
            changes_only = final[final['Διαφορά'] != 0].copy()
            
            # Sort: Οι μεγαλύτερες αυξήσεις/μειώσεις πρώτα (κατά απόλυτη τιμή)
            changes_only = changes_only.sort_values(by='Διαφορά', key=abs, ascending=False)

            # --- Display ---
            st.divider()
            st.success(f"✅ Εντοπίστηκαν **{len(changes_only)}** αλλαγές τιμών.")
            
            # Preview Table (Top 50)
            st.dataframe(
                changes_only.head(50).style.format({
                    'ΠΧΤ': '{:.2f}€', 'ΝΧΤ': '{:.2f}€', 'δ%': '{:+.2f}%', 'Διαφορά': '{:+.2f}€'
                }).background_gradient(subset=['Διαφορά'], cmap='RdYlGn_r') 
                # Το RdYlGn_r κάνει κόκκινο τις αυξήσεις (θετικές) και πράσινο τις μειώσεις (αρνητικές) - ή ανάποδα ανάλογα το business logic
            )

            # --- EXPORTS ---
            st.subheader("📥 Λήψη Αποτελεσμάτων")
            col_ex, col_pdf = st.columns(2)

            # 1. EXCEL (Μόνο οι αλλαγές)
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                # Εξάγουμε ΤΟ ΙΔΙΟ dataframe (changes_only)
                changes_only.to_excel(writer, index=False, sheet_name='PriceChanges')
                wb = writer.book
                ws = writer.sheets['PriceChanges']
                
                # Formats
                fmt_center = wb.add_format({'align': 'center', 'valign': 'vcenter'})
                fmt_eur = wb.add_format({'num_format': '#,##0.00€', 'align': 'center', 'valign': 'vcenter'})
                fmt_diff = wb.add_format({'num_format': '+#,##0.00€;-#,##0.00€;0.00€', 'align': 'center', 'valign': 'vcenter', 'bold': True})
                
                ws.set_column('A:A', 16, fmt_center)
                ws.set_column('B:B', 50, fmt_center)
                ws.set_column('C:D', 12, fmt_eur)
                ws.set_column('E:E', 10, fmt_center)
                ws.set_column('F:F', 12, fmt_diff)

                # Χρώματα (Κόκκινο > 0, Πράσινο < 0)
                ws.conditional_format('F2:F50000', {'type': 'cell', 'criteria': '>', 'value': 0, 
                                                    'format': wb.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})})
                ws.conditional_format('F2:F50000', {'type': 'cell', 'criteria': '<', 'value': 0, 
                                                    'format': wb.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})})

            with col_ex:
                st.download_button(
                    label=f"📄 Λήψη EXCEL ({len(changes_only)} είδη)",
                    data=buffer.getvalue(),
                    file_name="price_changes_only.xlsx",
                    mime="application/vnd.ms-excel",
                    type="primary"
                )

            # 2. PDF (Μόνο οι αλλαγές)
            with col_pdf:
                if len(changes_only) > 3000:
                    st.warning("⚠️ Πάνω από 3000 αλλαγές. Το PDF μπορεί να καθυστερήσει.")
                
                if st.button("📕 Δημιουργία PDF"):
                    with st.spinner("Γίνεται δημιουργία PDF..."):
                        try:
                            pdf_file = create_pdf_file(changes_only)
                            with open(pdf_file, "rb") as f:
                                pdf_bytes = f.read()
                                
                            st.download_button(
                                label="⬇️ Κλικ εδώ για κατέβασμα PDF",
                                data=pdf_bytes,
                                file_name="price_changes_report.pdf",
                                mime="application/pdf"
                            )
                            # Καθαρισμός temp αρχείου
                            os.remove(pdf_file)
                        except Exception as e:
                            st.error(f"Σφάλμα PDF: {e}")
