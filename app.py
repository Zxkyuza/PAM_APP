import streamlit as st
import pandas as pd
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# --- KONFIGURASI DASAR & KONEKSI GOOGLE SHEET ---

# Atur Judul dan ikon halaman
st.set_page_config(page_title="Data Tagihan Air", page_icon="💧", layout="wide")

# Definisikan konstanta (ubah sesuai kebutuhan Anda)
HARGA_PER_METER_KUBIK = 2500  # Contoh harga: Rp 2.500 per m³
NAMA_GOOGLE_SHEET = "Database Tagihan Air" # Nama file Google Sheet Anda
NAMA_WORKSHEET = "Sheet1" # Nama worksheet di dalam file

# Fungsi untuk koneksi ke Google Sheets menggunakan Streamlit Secrets
@st.cache_resource
def connect_to_gsheet():
    try:
        scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
        # Menggunakan file JSON secara langsung
        creds = Credentials.from_service_account_file(
            'credentials.json',
            scopes=scopes
        )
        gc = gspread.authorize(creds)
        spreadsheet = gc.open(NAMA_GOOGLE_SHEET)
        worksheet = spreadsheet.worksheet(NAMA_WORKSHEET)
        return worksheet
    except FileNotFoundError:
        st.error("File 'credentials.json' tidak ditemukan. Pastikan file tersebut berada di direktori yang sama dengan 'app.py'.")
        return None
    except Exception as e:
        st.error(f"Gagal terhubung ke Google Sheets. Pastikan API telah diaktifkan dan Sheet sudah di-share. Error: {e}")
        return None

# Fungsi untuk memuat data dari worksheet
# Fungsi untuk memuat data dari worksheet
@st.cache_data(ttl=5) # Cache data selama 5 detik
def load_data(_worksheet):
    if _worksheet:
        try:
            df = get_as_dataframe(_worksheet, parse_dates=True, header=0)
            # Menghapus baris yang semua isinya kosong
            df.dropna(how='all', inplace=True)
            # Konversi kolom numerik, jika error ubah ke 0
            numeric_cols = [
                'JUMLAH METER BULAN LALU', 'JUMLAH METER BULAN INI',
                'TAGIHAN YANG SUDAH DI BAYAR BULAN INI', 'TUNGGAKAN DARI BULAN LALU'
            ]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except Exception as e:
            st.error(f"Gagal memuat data dari worksheet. Error: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


# Panggil fungsi koneksi
worksheet = connect_to_gsheet()
df = load_data(worksheet)

# --- TAMPILAN APLIKASI STREAMLIT ---

st.title("💧 Aplikasi Pendataan & Pembayaran Air Bersih")
st.markdown("---")

# Membuat tab untuk memisahkan fungsionalitas
tab1, tab2, tab3 = st.tabs(["📊 Dashboard & Data Pelanggan", "📝 Input & Pembayaran", "👤 Tambah Pelanggan Baru"])

with tab1:
    st.header("Dashboard Informasi")
    if not df.empty:
        total_pelanggan = df['KODE PELANGGAN'].nunique()
        # Hitung total tunggakan dari kolom 'TOTAL TAGIHAN (TERMASUK TUNGGAKAN)' dikurangi 'TAGIHAN YANG SUDAH DI BAYAR BULAN INI'
        # Ambil data entri terakhir untuk setiap pelanggan
        last_entries = df.loc[df.groupby('KODE PELANGGAN')['TANGGAL INPUT'].idxmax()]
        total_tunggakan = last_entries['TOTAL TAGIHAN (TERMASUK TUNGGAKAN)'].sum() - last_entries['TAGIHAN YANG SUDAH DI BAYAR BULAN INI'].sum()

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
        st.warning("Gagal memuat data. Periksa koneksi dan konfigurasi.")

with tab2:
    st.header("Input Pembayaran & Meteran Bulan Ini")
    if not df.empty:
        # Ambil daftar pelanggan unik
        daftar_pelanggan = df['NAMA'].unique().tolist()
        
        # Pilih pelanggan berdasarkan nama
        nama_pelanggan_terpilih = st.selectbox("Pilih Nama Pelanggan", options=daftar_pelanggan, index=None, placeholder="Ketik atau pilih nama...")

        if nama_pelanggan_terpilih:
            kode_pelanggan = df[df['NAMA'] == nama_pelanggan_terpilih]['KODE PELANGGAN'].iloc[0]
            
            # Ambil data terakhir pelanggan
            data_terakhir = df[df['KODE PELANGGAN'] == kode_pelanggan].sort_values(by='TANGGAL INPUT', ascending=False).iloc[0]

            st.info(f"Menampilkan data untuk: **{nama_pelanggan_terpilih}** (Kode: {kode_pelanggan})")

            with st.form("form_pembayaran"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Data Bulan Lalu**")
                    meter_lalu = st.number_input("Jumlah Meter Bulan Lalu (m³)", value=data_terakhir['JUMLAH METER BULAN INI'], disabled=True)
                    
                    # Hitung tunggakan dari data terakhir
                    tunggakan_lalu = data_terakhir['TOTAL TAGIHAN (TERMASUK TUNGGAKAN)'] - data_terakhir['TAGIHAN YANG SUDAH DI BAYAR BULAN INI']
                    st.metric("Tunggakan dari Bulan Lalu", f"Rp {tunggakan_lalu:,.0f}")

                with col2:
                    st.write("**Input Bulan Ini**")
                    meter_ini = st.number_input("Input Jumlah Meter Bulan Ini (m³)", min_value=float(meter_lalu), step=1.0)
                    bayar_bulan_ini = st.number_input("Jumlah yang Dibayar Bulan Ini (Rp)", min_value=0, step=1000)
                
                # Tombol submit
                submitted = st.form_submit_button("Simpan Data & Hitung Tagihan")

                if submitted:
                    # Validasi input
                    if meter_ini < meter_lalu:
                        st.error("Jumlah meter bulan ini tidak boleh lebih kecil dari bulan lalu.")
                    else:
                        # --- Proses Perhitungan ---
                        pemakaian_kubik = meter_ini - meter_lalu
                        tagihan_bulan_ini = pemakaian_kubik * HARGA_PER_METER_KUBIK
                        total_tagihan = tagihan_bulan_ini + tunggakan_lalu
                        sisa_tagihan_bulan_ini = total_tagihan - bayar_bulan_ini
                        
                        # Data baru yang akan disimpan
                        data_baru = {
                            'KODE PELANGGAN': kode_pelanggan,
                            'NAMA': nama_pelanggan_terpilih,
                            'KAMPUNG': data_terakhir['KAMPUNG'],
                            'RT/RW': data_terakhir['RT/RW'],
                            'JUMLAH METER BULAN LALU': meter_lalu,
                            'JUMLAH METER BULAN INI': meter_ini,
                            'JUMLAH METER DIGUNAKAN BULAN INI': pemakaian_kubik,
                            'TAGIHAN YANG HARUS DI BAYAR BULAN INI': tagihan_bulan_ini,
                            'TAGIHAN YANG SUDAH DI BAYAR BULAN INI': bayar_bulan_ini,
                            'SISA TAGIHAN BULAN INI': sisa_tagihan_bulan_ini, # Ini adalah sisa setelah pembayaran bulan ini
                            'TUNGGAKAN DARI BULAN LALU': tunggakan_lalu,
                            'TOTAL TAGIHAN (TERMASUK TUNGGAKAN)': total_tagihan,
                            'TANGGAL INPUT': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        
                        # Tampilkan hasil perhitungan sebelum simpan
                        st.success("Perhitungan Berhasil!")
                        st.json({
                            "Pemakaian Bulan Ini": f"{pemakaian_kubik} m³",
                            "Tagihan Murni Bulan Ini": f"Rp {tagihan_bulan_ini:,.0f}",
                            "Total Tagihan (Termasuk Tunggakan)": f"Rp {total_tagihan:,.0f}",
                            "Jumlah Dibayar": f"Rp {bayar_bulan_ini:,.0f}",
                            "Sisa Tagihan Sekarang": f"Rp {sisa_tagihan_bulan_ini:,.0f}"
                        })

                        # Simpan ke Google Sheet
                        try:
                            df_baru = pd.DataFrame([data_baru])
                            # Gabungkan dengan data lama untuk di-upload
                            updated_df = pd.concat([df, df_baru], ignore_index=True)
                            set_with_dataframe(worksheet, updated_df, include_index=False)
                            st.success("✅ Data berhasil disimpan ke Google Sheets!")
                            st.balloons()
                            st.info("Data di dashboard akan diperbarui secara otomatis.")
                            # Clear cache agar data langsung ter-update
                            st.cache_data.clear()
                        except Exception as e:
                            st.error(f"Gagal menyimpan data ke Google Sheets. Error: {e}")
    else:
        st.warning("Belum ada data pelanggan. Silakan tambahkan pelanggan baru terlebih dahulu di tab 'Tambah Pelanggan Baru'.")

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
                # Data pelanggan baru
                data_pelanggan_baru = {
                    'KODE PELANGGAN': kode_pelanggan_baru,
                    'NAMA': nama_baru,
                    'KAMPUNG': kampung_baru,
                    'RT/RW': rtrw_baru,
                    'JUMLAH METER BULAN LALU': 0,
                    'JUMLAH METER BULAN INI': meter_awal,
                    'JUMLAH METER DIGUNAKAN BULAN INI': 0, # Pemakaian awal 0
                    'TAGIHAN YANG HARUS DI BAYAR BULAN INI': 0, # Tagihan awal 0
                    'TAGIHAN YANG SUDAH DI BAYAR BULAN INI': 0,
                    'SISA TAGIHAN BULAN INI': 0,
                    'TUNGGAKAN DARI BULAN LALU': 0,
                    'TOTAL TAGIHAN (TERMASUK TUNGGAKAN)': 0,
                    'TANGGAL INPUT': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                try:
                    df_baru = pd.DataFrame([data_pelanggan_baru])
                    # Gabungkan dengan data lama
                    updated_df = pd.concat([df, df_baru], ignore_index=True)
                    set_with_dataframe(worksheet, updated_df, include_index=False)
                    st.success(f"✅ Pelanggan baru '{nama_baru}' berhasil ditambahkan!")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"Gagal menyimpan data ke Google Sheets. Error: {e}")