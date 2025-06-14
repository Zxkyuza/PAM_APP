import streamlit as st
import pandas as pd
from gspread_dataframe import get_as_dataframe
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import uuid

# --- BASIC CONFIG & GOOGLE SHEETS CONNECTION ---

st.set_page_config(page_title="Data Tagihan Air", page_icon="💧", layout="wide")

# Constants
HARGA_PER_METER_KUBIK = 2500  # Rp 2,500 per m³
NAMA_GOOGLE_SHEET = "Database Tagihan Air"
NAMA_WORKSHEET = "Sheet1"

# Function to connect to Google Sheets
@st.cache_resource
def connect_to_gsheet():
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds = Credentials.from_service_account_file(
            'credentials.json',
            scopes=scopes
        )
        gc = gspread.authorize(creds)
        spreadsheet = gc.open(NAMA_GOOGLE_SHEET)
        worksheet = spreadsheet.worksheet(NAMA_WORKSHEET)
        return worksheet
    except FileNotFoundError:
        st.error("File 'credentials.json' not found. Ensure it’s in the same directory as 'app.py'.")
        return None
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets. Ensure API is enabled and Sheet is shared. Error: {e}")
        return None

# Function to load data from worksheet
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_data(_worksheet):
    if _worksheet:
        try:
            df = get_as_dataframe(
                _worksheet,
                parse_dates=['TANGGAL INPUT'],
                header=0,
                usecols=[
                    'KODE PELANGGAN', 'NAMA', 'KAMPUNG', 'RT/RW',
                    'JUMLAH METER BULAN LALU', 'JUMLAH METER BULAN INI',
                    'JUMLAH METER DIGUNAKAN BULAN INI',
                    'TAGIHAN YANG HARUS DI BAYAR BULAN INI',
                    'TAGIHAN YANG SUDAH DI BAYAR BULAN INI',
                    'SISA TAGIHAN BULAN INI', 'TUNGGAKAN DARI BULAN LALU',
                    'TOTAL TAGIHAN (TERMASUK TUNGGAKAN)', 'TANGGAL INPUT'
                ]
            )
            df.dropna(how='all', inplace=True)
            numeric_cols = [
                'JUMLAH METER BULAN LALU', 'JUMLAH METER BULAN INI',
                'JUMLAH METER DIGUNAKAN BULAN INI',
                'TAGIHAN YANG HARUS DI BAYAR BULAN INI',
                'TAGIHAN YANG SUDAH DI BAYAR BULAN INI',
                'SISA TAGIHAN BULAN INI', 'TUNGGAKAN DARI BULAN LALU',
                'TOTAL TAGIHAN (TERMASUK TUNGGAKAN)'
            ]
            for col in numeric_cols:
                if col in df.columns and df[col].dtype != 'float64':
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            st.error(f"Failed to load data from worksheet. Error: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# Initialize session state
if 'selected_customer' not in st.session_state:
    st.session_state.selected_customer = None

# Connect and load data
worksheet = connect_to_gsheet()
df = load_data(worksheet)

# --- STREAMLIT APP UI ---

st.title("💧 Aplikasi Pendataan & Pembayaran Air Bersih")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📊 Dashboard & Data Pelanggan", "📝 Input & Pembayaran", "👤 Tambah Pelanggan Baru"])

with tab1:
    st.header("Dashboard Informasi")
    if not df.empty:
        total_pelanggan = df['KODE PELANGGAN'].nunique()
        last_entries = df.loc[df.groupby('KODE PELANGGAN')['TANGGAL INPUT'].idxmax()]
        total_tunggakan = (
            last_entries['TOTAL TAGIHAN (TERMASUK TUNGGAKAN)'].sum() -
            last_entries['TAGIHAN YANG SUDAH DI BAYAR BULAN INI'].sum()
        )

        col1, col2 = st.columns(2)
        col1.metric("Jumlah Pelanggan Aktif", f"{total_pelanggan} orang")
        col2.metric("Estimasi Total Tunggakan Saat Ini", f"Rp {total_tunggakan:,.0f}")

    st.header("Data Seluruh Pelanggan")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    if worksheet:
        st.dataframe(df.style.format({
            'TAGIHAN YANG HARUS DI BAYAR BULAN INI': 'Rp {:,.0f}',
            'TAGIHAN YANG SUDAH DI BAYAR BULAN INI': 'Rp {:,.0f}',
            'SISA TAGIHAN BULAN INI': 'Rp {:,.0f}',
            'TUNGGAKAN DARI BULAN LALU': 'Rp {:,.0f}',
            'TOTAL TAGIHAN (TERMASUK TUNGGAKAN)': 'Rp {:,.0f}',
        }, na_rep='-'))
    else:
        st.warning("Failed to load data. Check connection and configuration.")

with tab2:
    st.header("Input Pembayaran & Meteran Bulan Ini")
    if not df.empty:
        daftar_pelanggan = df['NAMA'].unique().tolist()
        nama_pelanggan_terpilih = st.selectbox(
            "Pilih Nama Pelanggan",
            options=daftar_pelanggan,
            index=None,
            placeholder="Ketik atau pilih nama...",
            key='selected_customer'
        )

        if nama_pelanggan_terpilih:
            kode_pelanggan = df[df['NAMA'] == nama_pelanggan_terpilih]['KODE PELANGGAN'].iloc[0]
            data_terakhir = df[df['KODE PELANGGAN'] == kode_pelanggan].sort_values(by='TANGGAL INPUT', ascending=False).iloc[0]

            st.info(f"Menampilkan data untuk: **{nama_pelanggan_terpilih}** (Kode: {kode_pelanggan})")

            with st.form("form_pembayaran"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Data Bulan Lalu**")
                    meter_lalu = st.number_input(
                        "Jumlah Meter Bulan Lalu (m³)",
                        value=float(data_terakhir['JUMLAH METER BULAN INI']),
                        disabled=True
                    )
                    tunggakan_lalu = (
                        data_terakhir['TOTAL TAGIHAN (TERMASUK TUNGGAKAN)'] -
                        data_terakhir['TAGIHAN YANG SUDAH DI BAYAR BULAN INI']
                    )
                    st.metric("Tunggakan dari Bulan Lalu", f"Rp {tunggakan_lalu:,.0f}")

                with col2:
                    st.write("**Input Bulan Ini**")
                    meter_ini = st.number_input("Input Jumlah Meter Bulan Ini (m³)", min_value=meter_lalu, step=1.0)
                    bayar_bulan_ini = st.number_input("Jumlah yang Dibayar Bulan Ini (Rp)", min_value=0, step=1000)

                submitted = st.form_submit_button("Simpan Data & Hitung Tagihan")

                if submitted:
                    if meter_ini < meter_lalu:
                        st.error("Jumlah meter bulan ini tidak boleh lebih kecil dari bulan lalu.")
                    else:
                        pemakaian_kubik = meter_ini - meter_lalu
                        tagihan_bulan_ini = pemakaian_kubik * HARGA_PER_METER_KUBIK
                        total_tagihan = tagihan_bulan_ini + tunggakan_lalu
                        sisa_tagihan_bulan_ini = total_tagihan - bayar_bulan_ini

                        data_baru = [
                            kode_pelanggan,
                            nama_pelanggan_terpilih,
                            data_terakhir['KAMPUNG'],
                            data_terakhir['RT/RW'],
                            meter_lalu,
                            meter_ini,
                            pemakaian_kubik,
                            tagihan_bulan_ini,
                            bayar_bulan_ini,
                            sisa_tagihan_bulan_ini,
                            tunggakan_lalu,
                            total_tagihan,
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        ]

                        st.success("Perhitungan Berhasil!")
                        st.json({
                            "Pemakaian Bulan Ini": f"{pemakaian_kubik} m³",
                            "Tagihan Murni Bulan Ini": f"Rp {tagihan_bulan_ini:,.0f}",
                            "Total Tagihan (Termasuk Tunggakan)": f"Rp {total_tagihan:,.0f}",
                            "Jumlah Dibayar": f"Rp {bayar_bulan_ini:,.0f}",
                            "Sisa Tagihan Sekarang": f"Rp {sisa_tagihan_bulan_ini:,.0f}"
                        })

                        try:
                            worksheet.append_row(data_baru, value_input_option='USER_ENTERED')
                            st.success("✅ Data berhasil disimpan ke Google Sheets!")
                            st.balloons()
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Gagal menyimpan data ke Google Sheets. Error: {e}")
    else:
        st.warning("Belum ada data pelanggan. Tambahkan pelanggan baru di tab 'Tambah Pelanggan Baru'.")

with tab3:
    st.header("Form Pendaftaran Pelanggan Baru")
    with st.form("form_pelanggan_baru", clear_on_submit=True):
        kode_pelanggan_baru = st.text_input("Kode Pelanggan (Contoh: A001)")
        nama_baru = st.text_input("Nama Lengkap")
        kampung_baru = st.text_input("Kampung")
        rtrw_baru = st.text_input("RT/RW (Contoh: 001/002)")
        meter_awal = st.number_input("Angka Awal di Meteran (m³)", min_value=0.0, step=1.0)

        submitted_baru = st.form_submit_button("Daftarkan Pelanggan")

        if submitted_baru:
            if not all([kode_pelanggan_baru, nama_baru, kampung_baru, rtrw_baru]):
                st.error("Semua field harus diisi.")
            elif not df.empty and kode_pelanggan_baru in df['KODE PELANGGAN'].values:
                st.error("Kode Pelanggan sudah ada. Gunakan kode unik.")
            else:
                data_pelanggan_baru = [
                    kode_pelanggan_baru,
                    nama_baru,
                    kampung_baru,
                    rtrw_baru,
                    0,
                    meter_awal,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]

                try:
                    worksheet.append_row(data_pelanggan_baru, value_input_option='USER_ENTERED')
                    st.success(f"✅ Pelanggan baru '{nama_baru}' berhasil ditambahkan!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Gagal menyimpan data ke Google Sheets. Error: {e}")
