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

def transliterate_greek(text):
    """Μετατρέπει τα Ελληνικά σε Greeklish για Fallback στο PDF"""
    if not isinstance(text, str): return str(text)
    
    greek_to_latin = {
        'α': 'a', 'β': 'v', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'i', 'θ': 'th',
        'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p',
        'ρ': 'r', 'σ': 's', 'τ': 't', 'υ': 'y', 'φ': 'f', 'χ': 'ch', 'ψ': 'ps', 'ω': 'o',
        'ς': 's',
        'Α': 'A', 'Β': 'V', 'Γ': 'G', 'Δ': 'D', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'I', 'Θ': 'TH',
        'Ι': 'I', 'Κ': 'K', 'Λ': 'L', 'Μ': 'M', 'Ν': 'N', 'Ξ': 'X', 'Ο': 'O', 'Π': 'P',
        'Ρ': 'R', 'Σ': 'S', 'Τ': 'T', 'Υ': 'Y', 'Φ': 'F', 'Χ': 'CH', 'Ψ': 'PS', 'Ω': 'O',
        'ά': 'a', 'έ': 'e', 'ή': 'i', 'ί': 'i', 'ό': 'o', 'ύ': 'y', 'ώ': 'o',
        'Ά': 'A', 'Έ': 'E', 'Ή': 'I', 'Ί': 'I', 'Ό': 'O', 'Ύ': 'Y', 'Ώ': 'O',
        'ϊ': 'i', 'ϋ': 'y', 'ΐ': 'i', 'ΰ': 'y'
    }
    
    result = ""
    for char in text:
        result += greek_to_latin.get(char, char)
    return result

def find_wholesale_column(columns, must_have, must_not_have=None):
    if must_not_have is None: must_not_have = []
    for col in columns:
        norm_col = normalize_text(col)
        contains_all = all(normalize_text(k) in norm_col for k in must_have)
        contains_forbidden = any(normalize_text(k) in norm_col for k in must_not_have)
        if contains_all and not contains_forbidden:
            return col
    return None

def find_column_containing(columns, keywords):
    """Ψάχνει στήλη που περιέχει έστω ΜΙΑ από τις λέξεις κλειδιά"""
    for col in columns:
        norm_col = normalize_text(col)
        if any(normalize_text(k) in norm_col for k in keywords):
            return col
    return None

def find_exact_column(columns, target_keywords):
    for col in columns:
        norm_col = normalize_text(col)
        if all(normalize_text(k) in norm_col for k in target_keywords):
            return col
    return None

# --- ΦΟΡΤΩΣΗ & ΕΠΕΞΕΡΓΑΣΙΑ ΔΕΔΟΜΕΝΩΝ ---

@st.cache_data
def load_excel(file):
    try:
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Σφάλμα κατά την ανάγνωση αρχείου: {e}")
        return None

@st.cache_data
def process_comparison(df_old, df_new):
    # 1. Εντοπισμός Στηλών
    col_barcode_old = find_exact_column(df_old.columns, ['BARCODE'])
    col_barcode_new = find_exact_column(df_new.columns, ['BARCODE'])
    col_name = find_exact_column(df_new.columns, ['ΠΡΟΙΟΝ'])
    
    # Αναζήτηση στήλης Δραστικής (ψάχνουμε "Δραστική" ή "Active" ή "Substance")
    col_active = find_column_containing(df_new.columns, ['ΔΡΑΣΤΙΚΗ', 'ACTIVE', 'SUBSTANCE', 'INN'])
    
    col_price_old = find_wholesale_column(df_old.columns, 
                                        must_have=['ΧΟΝΔΡΙΚΗ', 'ΤΙΜΗ'], 
                                        must_not_have=['ΛΙΑΝΙΚΗ', 'RETAIL'])
    
    col_price_new = find_wholesale_column(df_new.columns, 
                                        must_have=['ΠΡΟΤΕΙΝΟΜΕΝΗ', 'ΧΟΝΔΡΙΚΗ'], 
                                        must_not_have=['ΛΙΑΝΙΚΗ', 'RETAIL'])

    # Fallback για τιμή
    if not col_price_new:
        col_price_new = find_wholesale_column(df_new.columns, 
                                            must_have=['ΧΟΝΔΡΙΚΗ'], 
                                            must_not_have=['ΛΙΑΝΙΚΗ'])

    if not (col_barcode_old and col_barcode_new and col_price_old and col_price_new):
        return None, "Δεν βρέθηκαν οι στήλες Barcode ή Χονδρικής Τιμής."

    st.info(f"✅ Ταύτιση Στηλών: **{col_price_old}** (Παλιό) vs **{col_price_new}** (Νέο)")
    if col_active:
        st.info(f"💊 Δραστική: **{col_active}**")

    # 2. Προετοιμασία DataFrames
    d1 = df_old[[col_barcode_old, col_price_old]].copy()
    d1.columns = ['Barcode', 'Old_XT']
    
    # Αν βρέθηκε δραστική την παίρνουμε, αλλιώς βάζουμε κενό
    if col_active:
        d2 = df_new[[col_barcode_new, col_name, col_active, col_price_new]].copy()
        d2.columns = ['Barcode', 'Name', 'Active', 'New_XT']
    else:
        d2 = df_new[[col_barcode_new, col_name, col_price_new]].copy()
        d2.columns = ['Barcode', 'Name', 'New_XT']
        d2['Active'] = '-'

    # 3. Καθαρισμός
    for df_temp in [d1, d2]:
        t_col = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
        
        if df_temp[t_col].dtype == object:
            df_temp[t_col] = df_temp[t_col].astype(str).str.replace(',', '.', regex=False)
            df_temp[t_col] = pd.to_numeric(df_temp[t_col], errors='coerce')
        df_temp[t_col] = df_temp[t_col].fillna(0)
        
        df_temp['Barcode'] = df_temp['Barcode'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
        df_temp.drop_duplicates(subset=['Barcode'], keep='first', inplace=True)

    # 4. Ένωση
    merged = pd.merge(d2, d1, on='Barcode', how='left')

    # 5. Υπολογισμοί
    merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
    merged['Diff_Pct'] = merged.apply(
        lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
    )

    # 6. Τελική Μορφή (Προσθήκη Δραστικής)
    final = merged[['Barcode', 'Name', 'Active', 'Old_XT', 'New_XT', 'Diff_Val', 'Diff_Pct']].copy()
    final.columns = ['Barcode', 'Όνομα Φαρμάκου', 'Δραστική', 'Παλιά ΧΤ', 'Νέα ΧΤ', 'Διαφορά', 'δ%']
    
    # Καθαρισμός κενών στη Δραστική
    final['Δραστική'] = final['Δραστική'].fillna('').astype(str)

    for c in ['Παλιά ΧΤ', 'Νέα ΧΤ', 'Διαφορά', 'δ%']:
        final[c] = final[c].round(2)

    return final, None

# --- PDF GENERATOR ---

def download_font(font_path):
    """Λήψη γραμματοσειράς"""
    url = "https://raw.githubusercontent.com/google/fonts/main/apache/roboto/Roboto-Regular.ttf"
    try:
        r = requests.get(url, allow_redirects=True, timeout=15)
        if r.status_code == 200 and len(r.content) > 10000:
            with open(font_path, 'wb') as f:
                f.write(r.content)
            return True
    except:
        pass
    return False

def create_pdf_file(df):
    """Δημιουργία PDF με Δραστική"""
    
    font_filename = "Roboto-Regular.ttf"
    font_path = os.path.join(os.getcwd(), font_filename)
    
    if not os.path.exists(font_path):
        download_font(font_path)

    pdf = FPDF('L', 'mm', 'A4')
    pdf.add_page()
    
    font_loaded = False
    try:
        pdf.add_font("Roboto", fname=font_path)
        pdf.set_font("Roboto", size=8)
        font_loaded = True
    except:
        if os.path.exists(font_path): os.remove(font_path)
        if download_font(font_path):
            try:
                pdf.add_font("Roboto", fname=font_path)
                pdf.set_font("Roboto", size=8)
                font_loaded = True
            except: pass

    if not font_loaded:
        st.warning("⚠️ Η γραμματοσειρά δεν φορτώθηκε. Greeklish mode.")
        pdf.set_font("Helvetica", size=7)

    def safe_txt(text):
        if font_loaded: return str(text)
        return transliterate_greek(str(text))

    # Header
    pdf.set_font_size(14)
    header_text = f'Λίστα Αλλαγών Τιμών ({len(df)} είδη)'
    pdf.cell(0, 10, text=safe_txt(header_text), align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Table Header
    pdf.set_font_size(7) # Λίγο μικρότερη γραμματοσειρά για να χωρέσουν όλα
    pdf.set_fill_color(220, 220, 220)
    
    # Πλάτη στηλών (Σύνολο ~277mm)
    w_bar, w_name, w_act, w_pr, w_diff, w_pct = 28, 85, 50, 22, 22, 18
    
    headers = [
        ('Barcode', w_bar), ('Όνομα Φαρμάκου', w_name), ('Δραστική', w_act),
        ('Παλιά ΧΤ', w_pr), ('Νέα ΧΤ', w_pr), ('Διαφορά', w_diff), ('δ%', w_pct)
    ]

    for title, w in headers:
        pdf.cell(w, 8, text=safe_txt(title), border=1, align='C', fill=True)
    pdf.ln()

    total_rows = len(df)
    progress_bar = st.progress(0)
    
    # Rows
    for i, (_, row) in enumerate(df.iterrows()):
        if i % 50 == 0: progress_bar.progress(min(i / total_rows, 1.0))
            
        barcode = str(row['Barcode'])
        name = safe_txt(str(row['Όνομα Φαρμάκου'])[:45]) # Κόψιμο
        active = safe_txt(str(row['Δραστική'])[:30])     # Κόψιμο
        pxt = f"{row['Παλιά ΧΤ']:.2f}"
        nxt = f"{row['Νέα ΧΤ']:.2f}"
        dval = f"{row['Διαφορά']:+.2f}"
        dpct = f"{row['δ%']:+.1f}%"

        pdf.cell(w_bar, 6, text=barcode, border=1, align='C')
        pdf.cell(w_name, 6, text=name, border=1, align='L')
        pdf.cell(w_act, 6, text=active, border=1, align='L') # Νέα στήλη
        pdf.cell(w_pr, 6, text=pxt, border=1, align='C')
        pdf.cell(w_pr, 6, text=nxt, border=1, align='C')
        pdf.cell(w_diff, 6, text=dval, border=1, align='C')
        pdf.cell(w_pct, 6, text=dpct, border=1, align='C', new_x="LMARGIN", new_y="NEXT")
    
    progress_bar.empty() 
    output_filename = "report_active.pdf"
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
            changes_only = final_df[final_df['Διαφορά'] != 0].copy()
            changes_only = changes_only.sort_values(by='Διαφορά', key=abs, ascending=False)
            
            st.divider()
            st.success(f"✅ Εντοπίστηκαν **{len(changes_only)}** αλλαγές τιμών.")
            st.info("💡 Μπορείτε να κάνετε **κλικ στις επικεφαλίδες** (Barcode, Δραστική, Διαφορά κλπ.) για να ταξινομήσετε τον πίνακα.")

            def color_diff(val):
                if val > 0: return 'color: #D32F2F; font-weight: bold;'
                elif val < 0: return 'color: #1B5E20; font-weight: bold;'
                return ''

            # Εμφάνιση πίνακα
            styled_df = changes_only.head(100).style.format({
                'Παλιά ΧΤ': '{:.2f}€', 'Νέα ΧΤ': '{:.2f}€', 
                'Διαφορά': '{:+.2f}€', 'δ%': '{:+.2f}%'
            }).map(color_diff, subset=['Διαφορά', 'δ%']) \
              .set_properties(**{'text-align': 'center'})

            st.dataframe(styled_df, use_container_width=True)

            # EXPORT
            st.subheader("📥 Λήψη Αρχείων")
            col_ex, col_pdf = st.columns(2)

            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                changes_only.to_excel(writer, index=False, sheet_name='Changes')
                wb = writer.book
                ws = writer.sheets['Changes']
                
                fmt_center = wb.add_format({'align': 'center', 'valign': 'vcenter'})
                fmt_eur = wb.add_format({'num_format': '#,##0.00€', 'align': 'center', 'valign': 'vcenter'})
                fmt_diff = wb.add_format({'num_format': '+#,##0.00€;-#,##0.00€;0.00€', 'align': 'center', 'valign': 'vcenter', 'bold': True})
                
                # A:Barcode, B:Name, C:Active, D:Old, E:New, F:Diff, G:Pct
                ws.set_column('A:A', 16, fmt_center)
                ws.set_column('B:B', 40, fmt_center)
                ws.set_column('C:C', 25, fmt_center) # Active
                ws.set_column('D:E', 12, fmt_eur)
                ws.set_column('F:F', 12, fmt_diff)
                ws.set_column('G:G', 10, fmt_center)

                ws.conditional_format('F2:F50000', {'type': 'cell', 'criteria': '>', 'value': 0, 'format': wb.add_format({'font_color': '#9C0006', 'bg_color': '#FFC7CE'})})
                ws.conditional_format('F2:F50000', {'type': 'cell', 'criteria': '<', 'value': 0, 'format': wb.add_format({'font_color': '#006100', 'bg_color': '#C6EFCE'})})

            with col_ex:
                st.download_button("📄 Λήψη EXCEL", buffer.getvalue(), "price_changes.xlsx", "application/vnd.ms-excel", type="primary")

            with col_pdf:
                if st.button("📕 Δημιουργία PDF"):
                    with st.spinner("Γίνεται δημιουργία PDF..."):
                        pdf_path = create_pdf_file(changes_only)
                        if pdf_path:
                            with open(pdf_path, "rb") as f:
                                st.download_button("⬇️ Κατέβασμα PDF", f.read(), "price_changes.pdf", "application/pdf")
                            os.remove(pdf_path)
