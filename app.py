import streamlit as st
import pandas as pd
from io import BytesIO
import unicodedata

# Ρυθμίσεις σελίδας
st.set_page_config(page_title="Σύγκριση Τιμών Φαρμάκων", page_icon="💊", layout="wide")

st.title("💊 Σύγκριση: Παλιά ΧΤ vs Προτεινόμενη ΧΤ")
st.markdown("""
Το πρόγραμμα θα διαβάσει τα αρχεία με βάση τις στήλες που δώσατε:
* **Κλειδί:** `Barcode`
* **Παλιό:** `Χονδρική Τιμή`
* **Νέο:** `Προτεινόμενη Χονδρική Τιμή`
""")

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
        # Ελέγχουμε αν ΟΛΕΣ οι λέξεις κλειδιά υπάρχουν στο όνομα της στήλης
        if all(normalize_text(k) in norm_col for k in target_keywords):
            return col
    return None

# --- Upload Files ---
st.write("---")
c1, c2 = st.columns(2)
old_file = c1.file_uploader("📂 ΠΑΛΙΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'])
new_file = c2.file_uploader("📂 ΝΕΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'])

if old_file and new_file:
    df_old = load_data(old_file)
    df_new = load_data(new_file)

    if df_old is not None and df_new is not None:
        
        # --- ΑΝΑΓΝΩΡΙΣΗ ΣΤΗΛΩΝ ΜΕ ΒΑΣΗ ΤΑ ΟΝΟΜΑΤΑ ΠΟΥ ΕΔΩΣΕΣ ---
        
        # 1. Barcode (Κλειδί)
        col_barcode_old = find_exact_column(df_old.columns, ['BARCODE'])
        col_barcode_new = find_exact_column(df_new.columns, ['BARCODE'])
        
        # 2. Όνομα Προϊόντος (Από το νέο αρχείο)
        col_name = find_exact_column(df_new.columns, ['ΠΡΟΙΟΝ'])
        
        # 3. Τιμές
        # Παλιό: "Χονδρική Τιμή"
        col_price_old = find_exact_column(df_old.columns, ['ΧΟΝΔΡΙΚΗ', 'ΤΙΜΗ']) 
        # Νέο: "Προτεινόμενη Χονδρική Τιμή"
        col_price_new = find_exact_column(df_new.columns, ['ΠΡΟΤΕΙΝΟΜΕΝΗ', 'ΧΟΝΔΡΙΚΗ'])

        # Έλεγχος αν βρέθηκαν
        if not col_barcode_old or not col_barcode_new or not col_price_old or not col_price_new:
            st.error("⚠️ Δεν βρέθηκαν οι στήλες! Βεβαιωθείτε ότι τα Excel έχουν τις ονομασίες: 'Barcode', 'Χονδρική Τιμή', 'Προτεινόμενη Χονδρική Τιμή'.")
        else:
            st.success(f"✅ Σύγκριση: **{col_price_old}** (Παλιό) vs **{col_price_new}** (Νέο)")

            # --- ΕΠΕΞΕΡΓΑΣΙΑ ---
            # Δημιουργία καθαρών DataFrames
            d1 = df_old[[col_barcode_old, col_price_old]].copy()
            d1.columns = ['Barcode', 'Old_XT']
            
            d2 = df_new[[col_barcode_new, col_name, col_price_new]].copy()
            d2.columns = ['Barcode', 'Name', 'New_XT']

            # Καθαρισμός Τιμών & Barcodes
            for df_temp in [d1, d2]:
                t_col = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
                
                # Τιμές: Αλλαγή , σε . και αριθμός
                if df_temp[t_col].dtype == object:
                    df_temp[t_col] = df_temp[t_col].astype(str).str.replace(',', '.', regex=False)
                    df_temp[t_col] = pd.to_numeric(df_temp[t_col], errors='coerce')
                df_temp[t_col] = df_temp[t_col].fillna(0)
                
                # Barcode: String χωρίς .0
                df_temp['Barcode'] = df_temp['Barcode'].astype(str).str.strip().str.replace('.0', '', regex=False)

            # Merge
            merged = pd.merge(d2, d1, on='Barcode', how='left')

            # Υπολογισμοί
            # Διαφορά (με πρόσημο)
            merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
            
            # Ποσοστό
            merged['Diff_Pct'] = merged.apply(
                lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
            )

            # --- ΤΕΛΙΚΟΣ ΠΙΝΑΚΑΣ ---
            final = merged[['Barcode', 'Name', 'Old_XT', 'New_XT', 'Diff_Pct', 'Diff_Val']].copy()
            final.columns = ['Barcode', 'Ονομασία', 'ΠΧΤ', 'ΝΧΤ', 'δ%', 'Διαφορά']
            
            # Στρογγυλοποίηση
            final['ΠΧΤ'] = final['ΠΧΤ'].round(2)
            final['ΝΧΤ'] = final['ΝΧΤ'].round(2)
            final['δ%'] = final['δ%'].round(2)
            final['Διαφορά'] = final['Διαφορά'].round(2)

            # --- ΠΡΟΒΟΛΗ ---
            st.divider()
            
            # Φιλτράρισμα για εμφάνιση μόνο των αλλαγών
            changes = final[final['Διαφορά'] != 0].sort_values(by='Διαφορά', ascending=False)
            
            st.subheader(f"📋 Βρέθηκαν {len(changes)} αλλαγές τιμών")
            
            # Εμφάνιση με custom styling στο Streamlit
            def color_diff(val):
                color = 'green' if val < 0 else 'red' if val > 0 else 'black'
                return f'color: {color}'

            st.dataframe(
                changes.head(50).style.format({
                    'ΠΧΤ': '{:.2f}€',
                    'ΝΧΤ': '{:.2f}€',
                    'δ%': '{:+.2f}%',
                    'Διαφορά': '{:+.2f}€'
                }).applymap(color_diff, subset=['Διαφορά', 'δ%'])
            )

            # --- EXCEL EXPORT (Με ειδική μορφοποίηση) ---
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                final.to_excel(writer, index=False, sheet_name='PriceChanges')
                wb = writer.book
                ws = writer.sheets['PriceChanges']
                
                # Formats
                fmt_eur = wb.add_format({'num_format': '#,##0.00€'})
                
                # ΕΙΔΙΚΟ FORMAT για να δείχνει + ή - (π.χ. +1.50€ ή -2.30€)
                fmt_diff_eur = wb.add_format({'num_format': '+#,##0.00€;-#,##0.00€;0.00€', 'bold': True})
                fmt_diff_pct = wb.add_format({'num_format': '+0.00%;-0.00%;0.00%'})
                
                # Στήλες
                ws.set_column('A:A', 16) # Barcode
                ws.set_column('B:B', 50) # Ονομασία
                ws.set_column('C:D', 12, fmt_eur) # ΠΧΤ, ΝΧΤ
                ws.set_column('E:E', 10, fmt_diff_pct) # δ%
                ws.set_column('F:F', 12, fmt_diff_eur) # Διαφορά (με πρόσημο)

                # Conditional Formatting στο Excel (Πράσινο για μείωση, Κόκκινο για αύξηση)
                # Προσοχή: Στα φάρμακα η αύξηση κόστους είναι αρνητική (κόκκινο), η μείωση θετική (πράσινο) ή το αντίθετο;
                # Συνήθως αύξηση τιμής = Κόκκινο, Μείωση = Πράσινο.
                
                ws.conditional_format('F2:F1048576', {
                    'type': 'cell',
                    'criteria': '>',
                    'value': 0,
                    'format': wb.add_format({'font_color': '#9C0006', 'bg_color': '#FFC7CE'}) # Red for increase
                })
                ws.conditional_format('F2:F1048576', {
                    'type': 'cell',
                    'criteria': '<',
                    'value': 0,
                    'format': wb.add_format({'font_color': '#006100', 'bg_color': '#C6EFCE'}) # Green for decrease
                })

            st.download_button(
                label="📥 ΛΗΨΗ EXCEL (με χρώματα και πρόσημα)",
                data=buffer.getvalue(),
                file_name="pharmacy_price_comparison.xlsx",
                mime="application/vnd.ms-excel",
                type="primary"
            )
