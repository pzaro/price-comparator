import streamlit as st
import pandas as pd

# Ρυθμίσεις σελίδας
st.set_page_config(page_title="Σύγκριση Τιμοκαταλόγων", page_icon="📊")

st.title("📊 Σύγκριση Δελτίων Τιμών")
st.write("Ανέβασε το παλιό και το νέο δελτίο τιμών (Excel) για να δεις τις διαφορές.")

# Συνάρτηση φόρτωσης αρχείων
def load_data(file):
    if file is not None:
        try:
            # Διαβάζουμε το excel
            df = pd.read_excel(file)
            return df
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None
    return None

# 1. Upload Αρχείων
col1, col2 = st.columns(2)
with col1:
    old_file = st.file_uploader("📂 Ανέβασε το ΠΑΛΙΟ δελτίο (.xlsx)", type=['xlsx', 'xls'])
with col2:
    new_file = st.file_uploader("📂 Ανέβασε το ΝΕΟ δελτίο (.xlsx)", type=['xlsx', 'xls'])

if old_file and new_file:
    # Φόρτωση των DataFrames
    df_old = load_data(old_file)
    df_new = load_data(new_file)

    if df_old is not None and df_new is not None:
        st.divider()
        st.subheader("⚙️ Ρυθμίσεις Στήλων")
        
        # Επιλογή στηλών από τον χρήστη (ώστε να δουλεύει με οποιοδήποτε format)
        col_list_old = df_old.columns.tolist()
        col_list_new = df_new.columns.tolist()

        c1, c2, c3, c4 = st.columns(4)
        
        # Επιλογή Κωδικού και Τιμής για το Παλιό
        key_old = c1.selectbox("Κωδικός (Παλιό)", col_list_old, index=0)
        price_old_col = c2.selectbox("Τιμή (Παλιό)", col_list_old, index=1 if len(col_list_old)>1 else 0)
        
        # Επιλογή Κωδικού και Τιμής για το Νέο
        key_new = c3.selectbox("Κωδικός (Νέο)", col_list_new, index=0)
        price_new_col = c4.selectbox("Τιμή (Νέο)", col_list_new, index=1 if len(col_list_new)>1 else 0)

        if st.button("🚀 Σύγκριση Τιμών"):
            # Προετοιμασία δεδομένων (κρατάμε μόνο τα απαραίτητα και μετονομάζουμε)
            df_old_clean = df_old[[key_old, price_old_col]].rename(columns={key_old: 'SKU', price_old_col: 'Old_Price'})
            df_new_clean = df_new[[key_new, price_new_col]].rename(columns={key_new: 'SKU', price_new_col: 'New_Price'})

            # Μετατροπή σε αριθμούς (σε περίπτωση που έχουν € ή είναι text)
            df_old_clean['Old_Price'] = pd.to_numeric(df_old_clean['Old_Price'], errors='coerce').fillna(0)
            df_new_clean['New_Price'] = pd.to_numeric(df_new_clean['New_Price'], errors='coerce').fillna(0)

            # Ένωση των δύο αρχείων (VLOOKUP logic)
            merged = pd.merge(df_new_clean, df_old_clean, on='SKU', how='left')

            # Υπολογισμοί
            # Αριθμητική διαφορά (Νέα Τιμή - Παλιά Τιμή)
            merged['Diff_Euro'] = merged['New_Price'] - merged['Old_Price']
            
            # Ποσοστιαία διαφορά
            merged['Diff_Percent'] = (merged['Diff_Euro'] / merged['Old_Price']) * 100
            
            # Καθαρισμός απείρων (αν η παλιά τιμή ήταν 0)
            merged['Diff_Percent'] = merged['Diff_Percent'].fillna(0).replace([float('inf'), -float('inf')], 0)

            # Δημιουργία κειμένου μορφοποίησης που ζήτησες: π.χ. "-1,50 ευρώ -7%"
            def format_diff(row):
                # Αν δεν υπάρχει διαφορά ή είναι νέο προϊόν
                if pd.isna(row['Old_Price']) or row['Old_Price'] == 0:
                    return "Νέο Είδος"
                
                euro_sign = "" if row['Diff_Euro'] < 0 else "+"
                pct_sign = "" if row['Diff_Percent'] < 0 else "+"
                
                return f"{euro_sign}{row['Diff_Euro']:.2f}€  {pct_sign}{row['Diff_Percent']:.1f}%"

            merged['Report'] = merged.apply(format_diff, axis=1)

            # Εμφάνιση αποτελεσμάτων
            st.success("Η σύγκριση ολοκληρώθηκε!")
            
            # Προβολή δείγματος
            st.write("Προεπισκόπηση αποτελεσμάτων:")
            st.dataframe(merged[['SKU', 'Old_Price', 'New_Price', 'Report']].head())

            # Download Button
            # Εξάγουμε όλα τα δεδομένα σε νέο Excel
            output_filename = "price_comparison_results.xlsx"
            
            # Χρησιμοποιούμε BytesIO για να γράψουμε το excel στη μνήμη
            from io import BytesIO
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                merged.to_excel(writer, index=False, sheet_name='Sheet1')
                
            download_data = buffer.getvalue()

            st.download_button(
                label="📥 Κατέβασε το Excel με τις διαφορές",
                data=download_data,
                file_name=output_filename,
                mime="application/vnd.ms-excel"
            )