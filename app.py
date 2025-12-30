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
st.markdown("Σύγκριση **Παλιάς Χονδρικής** με **Προτεινόμενη Χονδρική**.")

# --- ΣΥΝΑΡΤΗΣΕΙΣ ΒΟΗΘΗΤΙΚΕΣ ---

def normalize_text(text):
    """Καθαρίζει τόνους και κεφαλαία για ευκολότερη αναζήτηση"""
    if not isinstance(text, str): return str(text)
    text = text.upper()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def find_wholesale_column(columns, must_have, must_not_have=None):
    """
    Ψάχνει στήλη που ΠΡΕΠΕΙ να έχει συγκεκριμένες λέξεις (must_have)
    και ΑΠΑΓΟΡΕΥΕΤΑΙ να έχει άλλες (must_not_have), π.χ. Λιανική.
    """
    if must_not_have is None: must_not_have = []
    
    for col in columns:
        norm_col = normalize_text(col)
        # Έλεγχος 1: Να περιέχει ΟΛΕΣ τις λέξεις κλειδιά
        contains_all = all(normalize_text(k) in norm_col for k in must_have)
        # Έλεγχος 2: Να ΜΗΝ περιέχει καμία απαγορευμένη λέξη
        contains_forbidden = any(normalize_text(k) in norm_col for k in must_not_have)
        
        if contains_all and not contains_forbidden:
            return col
    return None

def find_exact_column(columns, target_keywords):
    """Απλή αναζήτηση για Barcode/Όνομα"""
    for col in columns:
        norm_col = normalize_text(col)
        if all(normalize_text(k) in norm_col for k in target_keywords):
            return col
    return None

# --- ΦΟΡΤΩΣΗ & ΕΠΕΞΕΡΓΑΣΙΑ ΔΕΔΟΜΕΝΩΝ (CACHED) ---

@st.cache_data
def load_excel(file):
    try:
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Σφάλμα κατά την ανάγνωση αρχείου: {e}")
        return None

@st.cache_data
def process_comparison(df_old, df_new):
    """Εκτελεί όλη τη λογική σύγκρισης"""
    
    # 1. Εντοπισμός Στηλών (Με ΑΥΣΤΗΡΟ φίλτρο για να μην πάρει Λιανικές)
    col_barcode_old = find_exact_column(df_old.columns, ['BARCODE'])
    col_barcode_new = find_exact_column(df_new.columns, ['BARCODE'])
    col_name = find_exact_column(df_new.columns, ['ΠΡΟΙΟΝ'])
    
    # Ψάχνουμε Χονδρική, ΑΠΑΓΟΡΕΥΟΥΜΕ τη λέξη Λιανική
    col_price_old = find_wholesale_column(df_old.columns, 
                                        must_have=['ΧΟΝΔΡΙΚΗ', 'ΤΙΜΗ'], 
                                        must_not_have=['ΛΙΑΝΙΚΗ', 'RETAIL'])
    
    col_price_new = find_wholesale_column(df_new.columns, 
                                        must_have=['ΠΡΟΤΕΙΝΟΜΕΝΗ', 'ΧΟΝΔΡΙΚΗ'], 
                                        must_not_have=['ΛΙΑΝΙΚΗ', 'RETAIL'])

    # Fallback: Αν δεν βρει 'ΠΡΟΤΕΙΝΟΜΕΝΗ', ψάχνει σκέτο 'Χονδρική' (χωρίς Λιανική)
    if not col_price_new:
        col_price_new = find_wholesale_column(df_new.columns, 
                                            must_have=['ΧΟΝΔΡΙΚΗ'], 
                                            must_not_have=['ΛΙΑΝΙΚΗ'])

    # Έλεγχος
    if not (col_barcode_old and col_barcode_new and col_price_old and col_price_new):
        return None, "Δεν βρέθηκαν οι στήλες. Βεβαιωθείτε ότι υπάρχουν: Barcode, Χονδρική Τιμή (όχι Λιανική)."

    # Εμφάνιση στο UI ποιες στήλες επιλέχθηκαν (για επιβεβαίωση χρήστη)
    st.info(f"✅ Σύγκριση: **{col_price_old}** (Παλιό) vs **{col_price_new}** (Νέο)")

    # 2. Προετοιμασία DataFrames
    d1 = df_old[[col_barcode_old, col_price_old]].copy()
    d1.columns = ['Barcode', 'Old_XT']
    
    d2 = df_new[[col_barcode_new, col_name, col_price_new]].copy()
    d2.columns = ['Barcode', 'Name', 'New_XT']

    # 3. Καθαρισμός
    for df_temp in [d1, d2]:
        t_col = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
        
        # Καθαρισμός Τιμής
        if df_temp[t_col].dtype == object:
            df_temp[t_col] = df_temp[t_col].astype(str).str.replace(',', '.', regex=False)
            df_temp[t_col] = pd.to_numeric(df_temp[t_col], errors='coerce')
        df_temp[t_col] = df_temp[t_col].fillna(0)
        
        # Καθαρισμός Barcode
        df_temp['Barcode'] = df_temp['Barcode'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

        # Αφαίρεση διπλοεγγραφών
        df_temp.drop_duplicates(subset=['Barcode'], keep='first', inplace=True)

    # 4. Ένωση
    merged = pd.merge(d2, d1, on='Barcode', how='left')

    # 5. Υπολογισμοί
    merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
    merged['Diff_Pct'] = merged.apply(
        lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
    )

    # 6. Τελική Μορφή (Η σειρά που ζήτησες)
    # Barcode | Ονομα φαρμακου | Παλιά ΧΤ | Νέα ΧΤ | Διαφορά | δ%
    final = merged[['Barcode', 'Name', 'Old_XT', 'New_XT', 'Diff_Val', 'Diff_Pct']].copy()
    final.columns = ['Barcode', 'Όνομα Φαρμάκου', 'Παλιά ΧΤ', 'Νέα ΧΤ', 'Διαφορά', 'δ%']
    
    # Στρογγυλοποίηση
    for c in ['Παλιά ΧΤ', 'Νέα ΧΤ', 'Διαφορά', 'δ%']:
        final[c] = final[c].round(2)

    return final, None

# --- PDF GENERATOR ---

def create_pdf_file(df):
    font_path = "Roboto-Regular.ttf"
    if not os.path.exists(font_path):
        try:
            url = "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Regular.ttf"
            r = requests.get(url, allow_redirects=True)
            with open(font_path, 'wb') as f: f.write(r.content)
        except: pass 

    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    try:
        pdf.add_font('Roboto', '', font_path, uni=True)
        pdf.set_font('Roboto', '', 8)
    except:
        pdf.set_font('Arial', '', 8)

    pdf.set_font_size(14)
    pdf.cell(0, 10, f'Λίστα Αλλαγών Τιμών ({len(df)} είδη)', 0, 1, 'C')
    pdf.ln(5)

    pdf.set_font_size(8)
    pdf.set_fill_color(220, 220, 220)
    
    # Στήλες και Πλάτη (Total ~275)
    # Barcode(30) Name(110) Old(25) New(25) Diff(25) Pct(20)
    w_bar, w_name, w_pr, w_diff, w_pct = 30, 110, 25, 25, 20
    
    # Header
    pdf.cell(w_bar, 8, 'Barcode', 1, 0, 'C', 1)
    pdf.cell(w_name, 8, 'Όνομα Φαρμάκου', 1, 0, 'C', 1)
    pdf.cell(w_pr, 8, 'Παλιά ΧΤ', 1, 0, 'C', 1)
    pdf.cell(w_pr, 8, 'Νέα ΧΤ', 1, 0, 'C', 1)
    pdf.cell(w_diff, 8, 'Διαφορά', 1, 0, 'C', 1)
    pdf.cell(w_pct, 8, 'δ%', 1, 1, 'C', 1)

    total_rows = len(df)
    progress_bar = st.progress(0)
    
    for i, (_, row) in enumerate(df.iterrows()):
        if i % 50 == 0: progress_bar.progress(min(i / total_rows, 1.0))
            
        barcode = str(row['Barcode'])
        name = str(row['Όνομα Φαρμάκου'])[:60]
        pxt = f"{row['Παλιά ΧΤ']:.2f}"
        nxt = f"{row['Νέα ΧΤ']:.2f}"
        dval = f"{row['Διαφορά']:+.2f}"
        dpct = f"{row['δ%']:+.1f}%"

        pdf.cell(w_bar, 6, barcode, 1, 0, 'C')
        pdf.cell(w_name, 6, name, 1, 0, 'L') 
        pdf.cell(w_pr, 6, pxt, 1, 0, 'C')
        pdf.cell(w_pr, 6, nxt, 1, 0, 'C')
        pdf.cell(w_diff, 6, dval, 1, 0, 'C') # Διαφορά
        pdf.cell(w_pct, 6, dpct, 1, 1, 'C') # Ποσοστό
    
    progress_bar.empty() 
    output_filename = "report_temp.pdf"
    pdf.output(output_filename)
    return output_filename

# --- ΚΥΡΙΩΣ APP LOGIC ---

st.write("---")
c1, c2 = st.columns(2)
old_file = c1.file_uploader("📂 ΠΑΛΙΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'])
new_file = c2.file_uploader("📂 ΝΕΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'])

if old_file and new_file:
    df_old = load_excel(old_file)
    df_new = load_excel(new_file)

    if df_old is not None and df_new is not None:
        final_df, error_msg = process_comparison(df_old, df_new)
        
        if error_msg:
            st.error(f"⚠️ {error_msg}")
        else:
            # Φίλτρο αλλαγών
            changes_only = final_df[final_df['Διαφορά'] != 0].copy()
            changes_only = changes_only.sort_values(by='Διαφορά', key=abs, ascending=False)
            
            # --- ΠΡΟΒΟΛΗ ---
            st.divider()
            st.success(f"✅ Εντοπίστηκαν **{len(changes_only)}** αλλαγές τιμών.")
            
            # CSS Styling
            def color_diff(val):
                if val > 0: return 'color: #D32F2F; font-weight: bold;'
                elif val < 0: return 'color: #1B5E20; font-weight: bold;'
                return ''

            styled_df = changes_only.head(100).style.format({
                'Παλιά ΧΤ': '{:.2f}€', 'Νέα ΧΤ': '{:.2f}€', 
                'Διαφορά': '{:+.2f}€', 'δ%': '{:+.2f}%'
            }).map(color_diff, subset=['Διαφορά', 'δ%']) \
              .set_properties(**{'text-align': 'center'})

            st.dataframe(styled_df, use_container_width=True)

            # --- EXPORT ---
            st.subheader("📥 Λήψη Αρχείων")
            col_ex, col_pdf = st.columns(2)

            # EXCEL
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                changes_only.to_excel(writer, index=False, sheet_name='Changes')
                wb = writer.book
                ws = writer.sheets['Changes']
                
                fmt_center = wb.add_format({'align': 'center', 'valign': 'vcenter'})
                fmt_eur = wb.add_format({'num_format': '#,##0.00€', 'align': 'center', 'valign': 'vcenter'})
                fmt_diff = wb.add_format({'num_format': '+#,##0.00€;-#,##0.00€;0.00€', 'align': 'center', 'valign': 'vcenter', 'bold': True})
                
                # Στήλες: Barcode(A), Name(B), Old(C), New(D), Diff(E), Pct(F)
                ws.set_column('A:A', 16, fmt_center)
                ws.set_column('B:B', 50, fmt_center)
                ws.set_column('C:D', 12, fmt_eur)
                ws.set_column('E:E', 12, fmt_diff)
                ws.set_column('F:F', 10, fmt_center)

                # Χρώματα στη Διαφορά (Στήλη E)
                ws.conditional_format('E2:E50000', {'type': 'cell', 'criteria': '>', 'value': 0, 'format': wb.add_format({'font_color': '#9C0006', 'bg_color': '#FFC7CE'})})
                ws.conditional_format('E2:E50000', {'type': 'cell', 'criteria': '<', 'value': 0, 'format': wb.add_format({'font_color': '#006100', 'bg_color': '#C6EFCE'})})

            with col_ex:
                st.download_button("📄 Λήψη EXCEL", buffer.getvalue(), "price_changes.xlsx", "application/vnd.ms-excel", type="primary")

            # PDF
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
