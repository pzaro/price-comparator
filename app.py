import streamlit as st
import pandas as pd
from io import BytesIO
import unicodedata

# Ρυθμίσεις σελίδας
st.set_page_config(page_title="Pharma Price Checker", page_icon="💊", layout="wide")

st.title("💊 Αυτόματη Σύγκριση Τιμών Φαρμάκων")
st.markdown("Το πρόγραμμα εντοπίζει αυτόματα τα Barcodes (που ξεκινούν από **280**) και συγκρίνει τις τιμές.")

# --- Βοηθητικές Συναρτήσεις ---

def normalize_text(text):
    """Καθαρίζει τόνους και κεφαλαία για αναζήτηση τίτλων"""
    if not isinstance(text, str): return str(text)
    text = text.upper()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def find_column_by_data_280(df):
    """Ψάχνει τα ΠΕΡΙΕΧΟΜΕΝΑ για να βρει ποια στήλη έχει Barcodes (280...)"""
    for col in df.columns:
        # Παίρνουμε δείγμα 20 εγγραφών (αγνοώντας κενά)
        sample = df[col].dropna().head(20).astype(str)
        # Μετράμε πόσα ξεκινούν από '280'
        matches = sample[sample.str.strip().str.startswith('280')]
        
        # Αν πάνω από το 50% του δείγματος ξεκινάει με 280, είναι η στήλη Barcode
        if len(sample) > 0 and len(matches) / len(sample) > 0.5:
            return col
    return None

def find_column_by_name(columns, keywords):
    """Ψάχνει τον ΤΙΤΛΟ της στήλης"""
    for col in columns:
        norm_col = normalize_text(col)
        for key in keywords:
            if key in norm_col:
                return col
    return None

def load_data(file):
    if file:
        try:
            return pd.read_excel(file)
        except Exception as e:
            st.error(f"Σφάλμα αρχείου: {e}")
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
        
        # --- ΕΞΥΠΝΗ ΑΝΑΓΝΩΡΙΣΗ ΣΤΗΛΩΝ ---
        
        # 1. Βήμα: Βρες το Barcode ψάχνοντας τα δεδομένα (Startswith 280)
        col_id_old = find_column_by_data_280(df_old)
        col_id_new = find_column_by_data_280(df_new)

        # Αν δεν βρει 280 (πχ παραφαρμακευτικά), ψάχνει με βάση το όνομα (Barcode/ΕΟΦ)
        if not col_id_old:
            col_id_old = find_column_by_name(df_old.columns, ['BARCODE', 'ΕΟΦ', 'ΚΩΔΙΚΟΣ', 'SKU'])
        if not col_id_new:
            col_id_new = find_column_by_name(df_new.columns, ['BARCODE', 'ΕΟΦ', 'ΚΩΔΙΚΟΣ', 'SKU'])

        # 2. Βήμα: Βρες Τιμές και Ονόματα με βάση τις επικεφαλίδες
        keys_name = ['ΠΕΡΙΓΡΑΦΗ', 'ΟΝΟΜΑΣΙΑ', 'ΕΙΔΟΣ', 'NAME', 'DESCR']
        keys_price = ['ΧΟΝΔΡΙΚΗ', 'ΧΤ', 'ΤΙΜΗ', 'PRICE', 'WHOLESALE']

        col_price_old = find_column_by_name(df_old.columns, keys_price)
        col_name_new = find_column_by_name(df_new.columns, keys_name)
        col_price_new = find_column_by_name(df_new.columns, keys_price)

        # Fallbacks (αν όλα αποτύχουν)
        if not col_id_old: col_id_old = df_old.columns[0]
        if not col_price_old: col_price_old = df_old.columns[-1]
        
        if not col_id_new: col_id_new = df_new.columns[0]
        if not col_name_new: col_name_new = df_new.columns[1] if len(df_new.columns)>1 else df_new.columns[0]
        if not col_price_new: col_price_new = df_new.columns[-1]

        # Εμφάνιση αποτελεσμάτων αναγνώρισης
        st.success(f"✅ Ταυτοποίηση: Παλιό Barcode: **{col_id_old}** | Νέο Barcode: **{col_id_new}**")

        # --- ΕΠΕΞΕΡΓΑΣΙΑ ---
        d1 = df_old[[col_id_old, col_price_old]].copy()
        d1.columns = ['Key', 'Old_XT']
        
        d2 = df_new[[col_id_new, col_name_new, col_price_new]].copy()
        d2.columns = ['Key', 'Name', 'New_XT']

        # Καθαρισμός Τιμών & Barcodes
        for df_temp in [d1, d2]:
            t_col = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
            
            # Καθαρισμός Τιμής
            if df_temp[t_col].dtype == object:
                df_temp[t_col] = df_temp[t_col].astype(str).str.replace(',', '.', regex=False)
                df_temp[t_col] = pd.to_numeric(df_temp[t_col], errors='coerce')
            df_temp[t_col] = df_temp[t_col].fillna(0)
            
            # Καθαρισμός Barcode (να είναι string χωρίς κενά)
            df_temp['Key'] = df_temp['Key'].astype(str).str.strip().str.replace('.0', '', regex=False)

        # Merge
        merged = pd.merge(d2, d1, on='Key', how='left')

        # Υπολογισμοί
        merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
        
        # Υπολογισμός % (μόνο αν υπάρχει παλιά τιμή)
        merged['Diff_Pct'] = merged.apply(
            lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
        )

        # --- ΤΕΛΙΚΗ ΜΟΡΦΟΠΟΙΗΣΗ (ΕΔΩ ΕΓΙΝΕ Η ΑΛΛΑΓΗ) ---
        final = merged[['Key', 'Name', 'Old_XT', 'New_XT', 'Diff_Pct', 'Diff_Val']].copy()
        
        # Οι νέες ονομασίες που ζήτησες
        final.columns = ['Barcode', 'Ονομασία', 'ΠΧΤ', 'ΝΧΤ', 'δ%', 'διαφορά']
        
        # Rounding
        cols_to_round = ['ΠΧΤ', 'ΝΧΤ', 'δ%', 'διαφορά']
        final[cols_to_round] = final[cols_to_round].round(2)

        # --- ΠΡΟΒΟΛΗ ---
        st.divider()
        col_res1, col_res2 = st.columns([3, 1])
        
        with col_res1:
            st.subheader("📋 Λίστα Διαφορών")
            # Δείχνουμε μόνο όσα έχουν διαφορά τιμής != 0
            changes_only = final[final['διαφορά'] != 0].sort_values(by='διαφορά', key=abs, ascending=False)
            
            if changes_only.empty:
                st.warning("Δεν βρέθηκαν αλλαγές τιμών!")
                st.dataframe(final.head())
            else:
                st.dataframe(changes_only.head(50)) # Δείχνουμε τις 50 πρώτες

        with col_res2:
            st.subheader("📊 Σύνοψη")
            increases = final[final['διαφορά'] > 0].shape[0]
            decreases = final[final['διαφορά'] < 0].shape[0]
            st.metric("Αυξήσεις", increases)
            st.metric("Μειώσεις", decreases)

        # --- EXPORT ---
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            final.to_excel(writer, index=False, sheet_name='PriceChanges')
            wb = writer.book
            ws = writer.sheets['PriceChanges']
            
            fmt_eur = wb.add_format({'num_format': '#,##0.00€'})
            fmt_pct = wb.add_format({'num_format': '0.00'})
            
            ws.set_column('A:A', 16) # Barcode
            ws.set_column('B:B', 50) # Ονομασία
            ws.set_column('C:D', 12, fmt_eur) # ΠΧΤ, ΝΧΤ
            ws.set_column('E:E', 10, fmt_pct) # δ%
            ws.set_column('F:F', 12, fmt_eur) # διαφορά

        st.download_button(
            label="📥 ΛΗΨΗ EXCEL",
            data=buffer.getvalue(),
            file_name="pharmacy_prices_diff.xlsx",
            mime="application/vnd.ms-excel",
            type="primary"
        )
