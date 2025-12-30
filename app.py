import streamlit as st
import pandas as pd
from io import BytesIO

# Ρυθμίσεις σελίδας
st.set_page_config(page_title="Έλεγχος Τιμών Φαρμάκων", page_icon="💊", layout="wide")

st.title("💊 Σύγκριση Τιμών Φαρμάκων (Barcode/ΕΟΦ)")
st.markdown("""
Ανεβάστε τα δύο αρχεία Excel (Παλιό & Νέο).  
Το πρόγραμμα θα ταιριάξει τα είδη με βάση το **Barcode ή τον Κωδικό ΕΟΦ** και θα υπολογίσει τις διαφορές στην **Χονδρική Τιμή (ΧΤ)**.
""")

def load_data(file):
    if file is not None:
        try:
            return pd.read_excel(file)
        except Exception as e:
            st.error(f"Σφάλμα στο αρχείο: {e}")
            return None
    return None

# Upload Section
c1, c2 = st.columns(2)
with c1:
    old_file = st.file_uploader("📂 ΠΑΛΙΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'], key="old")
with c2:
    new_file = st.file_uploader("📂 ΝΕΟ Δελτίο (.xlsx)", type=['xlsx', 'xls'], key="new")

if old_file and new_file:
    df_old = load_data(old_file)
    df_new = load_data(new_file)

    if df_old is not None and df_new is not None:
        st.divider()
        st.subheader("⚙️ Αντιστοίχιση Στηλών")
        st.info("Επέλεξε ποιες στήλες αντιστοιχούν στα δεδομένα σου.")

        cols_old = df_old.columns.tolist()
        cols_new = df_new.columns.tolist()

        # Επιλογές για το ταίριασμα
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**1. Κωδικός Ταυτοποίησης**")
            # Ο χρήστης επιλέγει αν θα ταιριάξει με Barcode ή ΕΟΦ
            key_old = st.selectbox("Στήλη Barcode/ΕΟΦ (Παλιό)", cols_old, index=0)
            key_new = st.selectbox("Στήλη Barcode/ΕΟΦ (Νέο)", cols_new, index=0)
        
        with col2:
            st.markdown("**2. Ονομασία Προϊόντος**")
            # Παίρνουμε την ονομασία από το Νέο αρχείο συνήθως
            name_col = st.selectbox("Στήλη Ονομασίας (από Νέο αρχείο)", cols_new, index=1 if len(cols_new)>1 else 0)
            
        with col3:
            st.markdown("**3. Χονδρική Τιμή (ΧΤ)**")
            price_old_col = st.selectbox("Στήλη ΧΤ (Παλιό)", cols_old, index=len(cols_old)-1)
            price_new_col = st.selectbox("Στήλη ΧΤ (Νέο)", cols_new, index=len(cols_new)-1)

        if st.button("🚀 Ανάλυση & Σύγκριση"):
            # Προετοιμασία DataFrames
            # Κρατάμε μόνο τα απαραίτητα και μετονομάζουμε για κοινή χρήση
            d1 = df_old[[key_old, price_old_col]].copy()
            d1.columns = ['Key', 'Old_XT']
            
            d2 = df_new[[key_new, name_col, price_new_col]].copy()
            d2.columns = ['Key', 'Name', 'New_XT']

            # Καθαρισμός Τιμών (μετατροπή σε αριθμούς, αφαίρεση συμβόλων € αν υπάρχουν)
            for df_temp in [d1, d2]:
                col_to_fix = 'Old_XT' if 'Old_XT' in df_temp.columns else 'New_XT'
                # Αν είναι string, αντικαθιστούμε κόμμα με τελεία και αφαιρούμε γράμματα
                if df_temp[col_to_fix].dtype == object:
                     df_temp[col_to_fix] = df_temp[col_to_fix].astype(str).str.replace(',', '.', regex=False)
                     df_temp[col_to_fix] = pd.to_numeric(df_temp[col_to_fix], errors='coerce')
                
                df_temp[col_to_fix] = df_temp[col_to_fix].fillna(0)

            # Merge (VLOOKUP) - Left join στο Νέο αρχείο για να δούμε τι άλλαξε στα τρέχοντα είδη
            merged = pd.merge(d2, d1, on='Key', how='left')

            # Υπολογισμοί
            merged['Diff_Val'] = merged['New_XT'] - merged['Old_XT']
            
            # Υπολογισμός ποσοστού (αποφυγή διαίρεσης με το 0)
            merged['Diff_Pct'] = merged.apply(
                lambda x: (x['Diff_Val'] / x['Old_XT'] * 100) if x['Old_XT'] > 0 else 0, axis=1
            )

            # Φιλτράρισμα: Κρατάμε μόνο όσα έχουν διαφορά τιμής (προαιρετικό - εδώ τα κρατάμε όλα αλλά σορτάρουμε τις αλλαγές)
            # Ή αν θέλεις ΜΟΝΟ τις αλλαγές, ξε-σχολίασε την επόμενη γραμμή:
            # merged = merged[merged['Diff_Val'] != 0]

            # Μορφοποίηση τελικού πίνακα για εξαγωγή
            final_df = merged[['Key', 'Name', 'Old_XT', 'New_XT', 'Diff_Pct', 'Diff_Val']].copy()
            final_df.columns = ['Barcode', 'Ονομασία Προϊόντος', 'Παλιά ΧΤ', 'Νέα ΧΤ', 'Δ%', 'Διαφορά']

            # Rounding για εμφάνιση
            final_df['Παλιά ΧΤ'] = final_df['Παλιά ΧΤ'].round(2)
            final_df['Νέα ΧΤ'] = final_df['Νέα ΧΤ'].round(2)
            final_df['Δ%'] = final_df['Δ%'].round(2)
            final_df['Διαφορά'] = final_df['Διαφορά'].round(2)

            # --- ΣΤΑΤΙΣΤΙΚΑ ---
            st.divider()
            st.subheader("📊 Σύνοψη Αλλαγών")
            increases = final_df[final_df['Διαφορά'] > 0].shape[0]
            decreases = final_df[final_df['Διαφορά'] < 0].shape[0]
            stable = final_df[final_df['Διαφορά'] == 0].shape[0]
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Αυξήσεις", increases, delta_color="inverse")
            m2.metric("Μειώσεις", decreases, delta_color="inverse")
            m3.metric("Αμετάβλητα", stable)

            # Προβολή
            st.write("Προεπισκόπηση λίστας (Top 10 αλλαγές):")
            # Δείχνουμε πρώτα αυτά που έχουν τη μεγαλύτερη διαφορά
            st.dataframe(final_df.sort_values(by='Διαφορά', ascending=False).head(10))

            # EXCEL DOWNLOAD
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False, sheet_name='PriceChanges')
                
                # Formatting στο Excel (ωραίο styling)
                workbook = writer.book
                worksheet = writer.sheets['PriceChanges']
                money_fmt = workbook.add_format({'num_format': '#,##0.00€'})
                pct_fmt = workbook.add_format({'num_format': '0.00%'})
                
                # Ορίζουμε το πλάτος των στηλών
                worksheet.set_column('A:A', 15) # Barcode
                worksheet.set_column('B:B', 40) # Name
                worksheet.set_column('C:D', 12, money_fmt) # XT Columns
                worksheet.set_column('E:E', 10, pct_fmt) # % Diff (Προσοχή: εδώ είναι αριθμός πχ 5.00, αν θες excel % πρέπει να διαιρέσεις με 100)
                worksheet.set_column('F:F', 12, money_fmt) # Value Diff

            st.download_button(
                label="📥 Κατέβασε τη λίστα (.xlsx)",
                data=buffer.getvalue(),
                file_name="pharmacy_price_changes.xlsx",
                mime="application/vnd.ms-excel"
            )
