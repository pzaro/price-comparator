import streamlit as st
import pandas as pd
from io import BytesIO
import unicodedata
from fpdf import FPDF
import requests
import os

# --- ΡΥΘΜΙΣΕΙΣ ΣΕΛΙΔΑΣ ---
st.set_page_config(page_title="Price Change Analyzer", page_icon="📉", layout="wide")
st.title("📉 Έλεγχος Αλλαγών Τιμών Φαρμάκων")

# --- ΣΥΝΑΡΤΗΣΕΙΣ ΒΟΗΘΗΤΙΚΕΣ ---

def normalize_text(text):
    """Καθαρίζει τόνους και κεφαλαία για ευκολότερη αναζήτηση"""
    if not isinstance(text, str): return str(text)
    text = text.upper()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def find_exact_column(columns, target_keywords):
    """Ψάχνει στήλη που περιέχει τις λέξεις κλειδιά"""
    for col in columns:
        norm_col = normalize_text(col)
        if all(normalize_text(k) in norm_col for k in target_keywords):
            return col
    return None

# --- ΦΟΡΤΩΣΗ & ΕΠΕΞΕΡΓΑΣΙΑ ΔΕΔΟΜΕΝΩΝ (CACHED) ---
# Το @st.cache_data κρατάει τα δεδομένα στη μνήμη για να μην τα ξαναφορτώνει όταν πατάς κουμπιά

@st.cache_data
def load_excel(file):
    try:
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Σφάλμα κατά την ανάγνωση αρχείου: {e}")
        return None

@st.cache_data
def process_comparison(df_old, df_new):
    """Εκτελεί όλη τη λογική σύγκρισης και επιστρέφει το τελικό DataFrame"""
    
    # Εντοπισμός Στηλών
    col_barcode_old = find_exact_column(df_old.columns, ['BARCODE'])
    col_barcode_new = find_exact_column(df_new.columns, ['BARCODE'])
    col_name = find_exact_column(df_new.columns, ['ΠΡΟΙΟΝ'])
    col_price_old = find_exact_column(df_old.columns, ['ΧΟΝΔΡΙΚΗ', 'ΤΙΜΗ']) 
    col_price_new = find_exact_column(df_new.columns, ['ΠΡΟΤΕΙΝΟΜΕΝΗ', 'ΧΟΝΔΡΙΚΗ'])

    # Έλεγχος αν βρέθηκαν όλα
    if not (col_barcode_old and col_barcode_new and col_price_old and col_price_new):
        return None, "Λείπουν απαραίτητες στήλες (Barcode, Χονδρική Τιμή, Προτεινόμενη Χονδρική)."

    # Προετοιμασία DataFrames
    d1 = df_old[[col_barcode_old, col_price_old]].copy()
    d1.columns = ['Barcode', 'Old_XT']
    
    d2 = df_new[[col_barcode_new, col_name, col_price_new]].copy()
    d2.columns = ['Barcode', 'Name', 'New_XT']

    # Καθαρισμός Τιμών & Barcode
    for df_temp in [d1, d2]:
        t_col = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
        
        # Τιμές: Αλλαγή , σε . και μετατροπή σε αριθμό
        if df_temp[t_col].dtype == object:
            df_temp[t_col] = df_temp[t_col].astype(str).str.replace(',', '.', regex=False)
            df_temp[t_col] = pd.to_numeric(df_temp[t_col], errors='coerce')
        df_temp[t_col] = df_temp[t_col].fillna(0)
        
        # Barcode: String, χωρίς κενά, χωρίς .0 στο τέλος
        df_temp['Barcode'] = df_temp['Barcode'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

    # Ένωση (Merge)
    merged = pd.merge(d2, d1, on='Barcode', how='left')

    # Υπολογισμοί
    merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
    merged['Diff_Pct'] = merged.apply(
        lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
    )

    # Μορφοποίηση Τελικού Πίνακα
    final = merged[['Barcode', 'Name', 'Old_XT', 'New_XT', 'Diff_Pct', 'Diff_Val']].copy()
    final.columns = ['Barcode', 'Ονομασία', 'ΠΧΤ', 'ΝΧΤ', 'δ%', 'Διαφορά']
    
    # Στρογγυλοποίηση
    for c in ['ΠΧΤ', 'ΝΧΤ', 'δ%', 'Διαφορά']:
        final[c] = final[c].round(2)

    return final, None

# --- PDF GENERATOR ---

def create_pdf_file(df):
    """Δημιουργεί PDF και επιστρέφει το path του αρχείου"""
    font_path = "Roboto-Regular.ttf"
    
    # Λήψη γραμματοσειράς αν δεν υπάρχει
    if not os.path.exists(font_path):
        try:
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf"
            r = requests.get(url, allow_redirects=True)
            with open(font_path, 'wb') as f:
                f.write(r.content)
        except:
            pass # Αν αποτύχει, θα χρησιμοποιήσει την default (χωρίς Ελληνικά)

    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    
    # Προσπάθεια φόρτωσης γραμματοσειράς
    try:
        pdf.add_font('Roboto', '', font_path, uni=True)
        pdf.set_font('Roboto', '', 8)
    except:
        pdf.set_font('Arial', '', 8)

    # Τίτλος
    pdf.set_font_size(14)
    pdf.cell(0, 10, f'Λίστα Αλλαγών Τιμών ({len(df)} είδη)', 0, 1, 'C')
    pdf.ln(5)

    # Header Πίνακα
    pdf.set_font_size(8)
    pdf.set_fill_color(220, 220, 220)
    
    # Cell Widths: Total ~275mm
    w_bar, w_name, w_pr, w_diff = 30, 120, 25, 25
    
    pdf.cell(w_bar, 8, 'Barcode', 1, 0, 'C', 1)
    pdf.cell(w_name, 8, 'Ονομασία', 1, 0, 'C', 1)
    pdf.cell(w_pr, 8, 'ΠΧΤ', 1, 0, 'C', 1)
    pdf.cell(w_pr, 8, 'ΝΧΤ', 1, 0, 'C', 1)
    pdf.cell(20, 8, 'δ%', 1, 0, 'C', 1)
    pdf.cell(w_diff, 8, 'Διαφορά', 1, 1, 'C', 1)

    # Rows (Με progress bar στο UI)
    total_rows = len(df)
    progress_bar = st.progress(0)
    
    for i, (_, row) in enumerate(df.iterrows()):
        # Update progress bar κάθε 50 εγγραφές για ταχύτητα
        if i % 50 == 0:
            progress_bar.progress(min(i / total_rows, 1.0))
            
        barcode = str(row['Barcode'])
        name = str(row['Ονομασία'])[:65]
        pxt = f"{row['ΠΧΤ']:.2f}"
        nxt = f"{row['ΝΧΤ']:.2f}"
        dpct = f"{row['δ%']:+.1f}%"
        dval = f"{row['Διαφορά']:+.2f}"

        pdf.cell(w_bar, 6, barcode, 1, 0, 'C')
        pdf.cell(w_name, 6, name, 1, 0, 'L') # Left align ονόματος
        pdf.cell(w_pr, 6, pxt, 1, 0, 'C')
        pdf.cell(w_pr, 6, nxt, 1, 0, 'C')
        pdf.cell(20, 6, dpct, 1, 0, 'C')
        pdf.cell(w_diff, 6, dval, 1, 1, 'C')
    
    progress_bar.empty() # Απόκρυψη μπάρας
    output_filename = "report_temp.pdf"
    pdf.output(output_filename)
    return output_filename

# --- ΚΥΡΙΩΣ APP LOGIC ---

st.write("---")
c1, c2 = st.columns(2)
old_file = c1.file_uploader("📂 ΠΑΛΙΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'])
new_file = c2.file_uploader("📂 ΝΕΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'])

if old_file and new_file:
    # 1. Φόρτωση
    df_old = load_excel(old_file)
    df_new = load_excel(new_file)

    if df_old is not None and df_new is not None:
        # 2. Επεξεργασία
        final_df, error_msg = process_comparison(df_old, df_new)
        
        if error_msg:
            st.error(f"⚠️ {error_msg}")
        else:
            # 3. Φιλτράρισμα Αλλαγών
            changes_only = final_df[final_df['Διαφορά'] != 0].copy()
            changes_only = changes_only.sort_values(by='Διαφορά', key=abs, ascending=False)
            
            # --- ΠΡΟΒΟΛΗ ---
            st.divider()
            st.success(f"✅ Εντοπίστηκαν **{len(changes_only)}** αλλαγές τιμών.")
            
            # Styling Function (Ελαφρύ, χωρίς matplotlib)
            def color_rows(val):
                if val > 0:
                    return 'color: #D32F2F; font-weight: bold;' # Κόκκινο για αυξήσεις
                elif val < 0:
                    return 'color: #1B5E20; font-weight: bold;' # Πράσινο για μειώσεις
                return ''

            # Εφαρμογή στυλ μόνο στις στήλες διαφοράς
            styled_df = changes_only.head(100).style.format({
                'ΠΧΤ': '{:.2f}€', 'ΝΧΤ': '{:.2f}€', 'δ%': '{:+.2f}%', 'Διαφορά': '{:+.2f}€'
            }).map(color_rows, subset=['δ%', 'Διαφορά']) \
              .set_properties(**{'text-align': 'center'})

            st.dataframe(styled_df, use_container_width=True)

            # --- EXPORT SECTION ---
            st.subheader("📥 Λήψη Αρχείων")
            col_ex, col_pdf = st.columns(2)

            # A. EXCEL
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                changes_only.to_excel(writer, index=False, sheet_name='Changes')
                wb = writer.book
                ws = writer.sheets['Changes']
                
                # Formats
                fmt_center = wb.add_format({'align': 'center', 'valign': 'vcenter'})
                fmt_eur = wb.add_format({'num_format': '#,##0.00€', 'align': 'center', 'valign': 'vcenter'})
                fmt_diff = wb.add_format({'num_format': '+#,##0.00€;-#,##0.00€;0.00€', 'align': 'center', 'valign': 'vcenter', 'bold': True})
                
                ws.set_column('A:A', 16, fmt_center)
                ws.set_column('B:B', 50, fmt_center)
                ws.set_column('C:D', 12, fmt_eur)
                ws.set_column('E:E', 10, fmt_center)
                ws.set_column('F:F', 12, fmt_diff)
                
                # Conditional Formatting (Excel Native)
                ws.conditional_format('F2:F50000', {'type': 'cell', 'criteria': '>', 'value': 0, 'format': wb.add_format({'font_color': '#9C0006', 'bg_color': '#FFC7CE'})})
                ws.conditional_format('F2:F50000', {'type': 'cell', 'criteria': '<', 'value': 0, 'format': wb.add_format({'font_color': '#006100', 'bg_color': '#C6EFCE'})})

            with col_ex:
                st.download_button("📄 Λήψη EXCEL", buffer.getvalue(), "price_changes.xlsx", "application/vnd.ms-excel", type="primary")

            # B. PDF
            with col_pdf:
                if st.button("📕 Δημιουργία PDF"):
                    with st.spinner("Γίνεται δημιουργία PDF..."):
                        try:
                            pdf_file = create_pdf_file(changes_only)
                            with open(pdf_file, "rb") as f:
                                st.download_button("⬇️ Κατέβασμα PDF", f.read(), "price_changes.pdf", "application/pdf")
                            os.remove(pdf_file)
                        except Exception as e:
                            st.error(f"Σφάλμα PDF: {e}")
