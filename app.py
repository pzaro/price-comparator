import streamlit as st
import pandas as pd
from io import BytesIO
import unicodedata

# Ρυθμίσεις σελίδας
st.set_page_config(page_title="Auto Price Checker", page_icon="⚡", layout="wide")

st.title("⚡ Αυτόματη Σύγκριση Τιμών Φαρμάκων")
st.markdown("Ανεβάστε τα αρχεία. Το πρόγραμμα θα εντοπίσει **αυτόματα** Barcode, Περιγραφή και Τιμές.")

# Συνάρτηση για αφαίρεση τόνων και κεφαλαία (για ευκολότερη αναζήτηση)
def normalize_text(text):
    if not isinstance(text, str): return str(text)
    text = text.upper()
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

# Η "έξυπνη" συνάρτηση που βρίσκει τη στήλη
def find_column(columns, keywords):
    # 1. Ψάχνει ακριβές ταίριασμα
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
c1, c2 = st.columns(2)
old_file = c1.file_uploader("📂 ΠΑΛΙΟ Δελτίο", type=['xlsx', 'xls'])
new_file = c2.file_uploader("📂 ΝΕΟ Δελτίο", type=['xlsx', 'xls'])

if old_file and new_file:
    df_old = load_data(old_file)
    df_new = load_data(new_file)

    if df_old is not None and df_new is not None:
        
        # --- ΑΥΤΟΜΑΤΗ ΑΝΑΓΝΩΡΙΣΗ ΣΤΗΛΩΝ ---
        # Λέξεις κλειδιά που ψάχνουμε (χωρίς τόνους, κεφαλαία)
        keys_id = ['BARCODE', 'ΕΟΦ', 'ΚΩΔΙΚΟΣ', 'CODE', 'SKU', 'EAN', 'ID']
        keys_name = ['ΠΕΡΙΓΡΑΦΗ', 'ΟΝΟΜΑΣΙΑ', 'ΕΙΔΟΣ', 'NAME', 'DESCRIPTION', 'TITLE']
        keys_price = ['ΧΟΝΔΡΙΚΗ', 'ΧΤ', 'ΤΙΜΗ', 'PRICE', 'WHOLESALE', 'COST']

        # Προσπάθεια εντοπισμού
        col_id_old = find_column(df_old.columns, keys_id)
        col_price_old = find_column(df_old.columns, keys_price)
        
        col_id_new = find_column(df_new.columns, keys_id)
        col_name_new = find_column(df_new.columns, keys_name)
        col_price_new = find_column(df_new.columns, keys_price)

        # Fallback: Αν δεν βρει λέξεις κλειδιά, παίρνει τις προεπιλεγμένες θέσεις
        # (Παλιό: 1η στήλη ID, Τελευταία Τιμή)
        if not col_id_old: col_id_old = df_old.columns[0]
        if not col_price_old: col_price_old = df_old.columns[-1]
        
        # (Νέο: 1η στήλη ID, 2η Όνομα, Τελευταία Τιμή)
        if not col_id_new: col_id_new = df_new.columns[0]
        if not col_name_new: col_name_new = df_new.columns[1] if len(df_new.columns) > 1 else df_new.columns[0]
        if not col_price_new: col_price_new = df_new.columns[-1]

        # Εμφάνιση στο χρήστη τι βρήκε (για επιβεβαίωση)
        st.info(f"""
        ✅ **Αναγνωρίστηκαν αυτόματα:**
        * **Ταύτιση βάσει:** `{col_id_new}`
        * **Παλιά Τιμή:** `{col_price_old}` (από αρχείο 1)
        * **Νέα Τιμή:** `{col_price_new}` (από αρχείο 2)
        """)

        # --- ΕΠΕΞΕΡΓΑΣΙΑ ---
        # Καθαρισμός δεδομένων
        d1 = df_old[[col_id_old, col_price_old]].copy()
        d1.columns = ['Key', 'Old_XT']
        
        d2 = df_new[[col_id_new, col_name_new, col_price_new]].copy()
        d2.columns = ['Key', 'Name', 'New_XT']

        # Convert Types (String to Float for prices)
        for df_temp in [d1, d2]:
            t_col = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
            # Αντικατάσταση , με . και μετατροπή σε αριθμό
            if df_temp[t_col].dtype == object:
                df_temp[t_col] = df_temp[t_col].astype(str).str.replace(',', '.', regex=False)
                df_temp[t_col] = pd.to_numeric(df_temp[t_col], errors='coerce')
            df_temp[t_col] = df_temp[t_col].fillna(0)
        
        # Βεβαιωνόμαστε ότι τα Κλειδιά (Barcode/ΕΟΦ) είναι string για να ταιριάξουν σωστά
        d1['Key'] = d1['Key'].astype(str).str.strip()
        d2['Key'] = d2['Key'].astype(str).str.strip()

        # Merge
        merged = pd.merge(d2, d1, on='Key', how='left')

        # Calculations
        merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
        merged['Diff_Pct'] = merged.apply(
            lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
        )

        # Final Formatting
        final = merged[['Key', 'Name', 'Old_XT', 'New_XT', 'Diff_Pct', 'Diff_Val']].copy()
        final.columns = ['Barcode/ΕΟΦ', 'Ονομασία Προϊόντος', 'Παλιά ΧΤ', 'Νέα ΧΤ', 'Δ%', 'Διαφορά']

        # Formatting values
        final['Παλιά ΧΤ'] = final['Παλιά ΧΤ'].round(2)
        final['Νέα ΧΤ'] = final['Νέα ΧΤ'].round(2)
        final['Δ%'] = final['Δ%'].round(2)
        final['Διαφορά'] = final['Διαφορά'].round(2)

        # Προβολή
        st.write("### Αποτελέσματα (Top αλλαγές)")
        st.dataframe(final.sort_values(by='Διαφορά', key=abs, ascending=False).head(10))

        # --- EXCEL EXPORT ---
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            final.to_excel(writer, index=False, sheet_name='PriceChanges')
            
            wb = writer.book
            ws = writer.sheets['PriceChanges']
            
            # Formats
            fmt_eur = wb.add_format({'num_format': '#,##0.00€'})
            fmt_pct = wb.add_format({'num_format': '0.00'}) # Αριθμός με 2 δεκαδικά
            
            # Auto-width columns (περίπου)
            ws.set_column('A:A', 15) # Barcode
            ws.set_column('B:B', 45) # Name
            ws.set_column('C:D', 12, fmt_eur) # Prices
            ws.set_column('E:E', 10, fmt_pct) # Pct
            ws.set_column('F:F', 12, fmt_eur) # Diff

        st.download_button(
            label="📥 Κατέβασε το Τελικό Αρχείο",
            data=buffer.getvalue(),
            file_name="apotelesmata_timon.xlsx",
            mime="application/vnd.ms-excel"
        )
