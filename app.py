import streamlit as st
import pandas as pd
import io
import chardet

st.title("Neoden YY1 SMD Dizgi Makinesi İçin Dosya Dönüştürücü")

st.markdown(
    """
    <style>
    div[data-testid='stTextInput'] input {
        height: 38px !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def read_flexible_csv(uploaded_file):
    # Dosyanın ilk 1024 baytını oku ve ayraç ile encoding tespit et
    sample = uploaded_file.read(1024)
    uploaded_file.seek(0)
    encoding = chardet.detect(sample)['encoding'] or 'utf-8'
    sample_str = sample.decode(encoding, errors='replace')
    # Ayraç tespiti
    delimiter = ','
    if sample_str.count(';') > sample_str.count(','):
        delimiter = ';'
    # DataFrame'i oku
    df = pd.read_csv(uploaded_file, delimiter=delimiter, encoding=encoding, dtype=str, quotechar='"')
    # Tüm hücrelerde baştaki ve sondaki boşlukları temizle
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    # Koordinatlarda mm varsa temizle ve ondalık karakteri düzelt
    for col in df.columns:
        if any(key in col.lower() for key in ['mid x', 'mid y']):
            df[col] = df[col].astype(str).str.replace('mm', '', case=False, regex=False)
            # Eğer ondalık virgül varsa noktaya çevir
            df[col] = df[col].str.replace(',', '.', regex=False)
            # Sayıya çevir
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # Diğer ondalıklı sayılar için de aynı işlemi uygula (ör: Pick Height, Place Height)
    for col in df.columns:
        if any(key in col.lower() for key in ['height', 'speed']):
            df[col] = df[col].astype(str).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(df[col], errors='coerce')
    # Geri kalan tüm hücrelerde baştaki ve sondaki çift tırnakları temizle
    df = df.applymap(lambda x: x[1:-1] if isinstance(x, str) and x.startswith('"') and x.endswith('"') else x)
    return df

def find_column(df, alternatives):
    # Sütun adlarını normalize et
    norm_cols = {col.strip().lower().replace(' ', '').replace('-', ''): col for col in df.columns}
    for alt in alternatives:
        norm_alt = alt.strip().lower().replace(' ', '').replace('-', '')
        if norm_alt in norm_cols:
            return norm_cols[norm_alt]
    return None

uploaded_file = st.file_uploader("CSV dosyanızı yükleyin", type=["csv"])

if uploaded_file:
    df = read_flexible_csv(uploaded_file)
    # Alternatif sütun isimlerini bul
    x_col = find_column(df, ["Mid X", "Mid X(mm)", "Center-X(mm)", "MidX"])
    y_col = find_column(df, ["Mid Y", "Mid Y(mm)", "Center-Y(mm)", "MidY"])
    designator_col = find_column(df, ["Designator", "Ref"])
    # Boş satırları (özellikle başlık altındaki) filtrele
    df = df.dropna(subset=["Comment", "Footprint"])
    df = df[(df["Comment"].astype(str).str.strip() != "") & (df["Footprint"].astype(str).str.strip() != "")]
    # (Comment, Footprint) ikilisine göre benzersiz parça listesi
    unique_parts = df[["Comment", "Footprint"]].drop_duplicates().reset_index(drop=True)
    unique_parts["Feeder"] = ""
    unique_parts["Nozzle"] = ""
    unique_parts["Pick Height"] = 0.0
    unique_parts["Place Height"] = 0.0
    unique_parts["Move Speed"] = 100
    unique_parts["Mode"] = 1
    unique_parts["Skip"] = 0
    st.write("### Komponent Listesi")
    # Kolon genişliklerini ayarlıyoruz: [parça, feeder, nozzle, pick, place, move, mode, skip]
    cols = st.columns([4.5, 1, 1, 2, 2, 2, 1, 1])
    headers = [
        "Parça Bilgisi",
        "Feeder",
        "Nozzle",
        "Pick Height",
        "Place Height",
        "Move Speed",
        "Mode",
        "Skip"
    ]
    for i, h in enumerate(headers):
        with cols[i]:
            st.markdown(f"<div style='text-align:center; font-weight:bold; white-space:nowrap; '>{h}</div>", unsafe_allow_html=True)
    for idx, row in unique_parts.iterrows():
        cols = st.columns([4.5, 1, 1, 2, 2, 2, 1, 1])  # Parça bilgisi sütunu daha geniş
        with cols[0]:
            st.markdown(
                f"<div style='display:flex; align-items:center; height:38px; padding-left:4px; margin-top:30px; font-weight:bold; border:1px solid #222; border-radius:4px; background-color:#111; color:#fff'>{row['Comment']} / {row['Footprint']}</div>",
                unsafe_allow_html=True
            )
        with cols[1]:
            feeder = st.text_input('', key=f'feeder_{idx}', max_chars=3)
        with cols[2]:
            nozzle = st.text_input('', key=f'nozzle_{idx}', max_chars=1)
        with cols[3]:
            pick_height = st.text_input('', key=f'pick_{idx}')
        with cols[4]:
            place_height = st.text_input('', key=f'place_{idx}')
        with cols[5]:
            move_speed = st.text_input('', key=f'movespeed_{idx}')
        with cols[6]:
            mode = st.text_input('', key=f'mode_{idx}')
        with cols[7]:
            skip = st.text_input('', key=f'skip_{idx}')
        # Feeder kontrolü
        try:
            feeder_val = int(feeder) if feeder.strip() != '' else 1
            if feeder_val < 1 or feeder_val > 100:
                st.warning(f"Feeder {row['Comment']} / {row['Footprint']} için 1 ile 100 arasında olmalı.")
                feeder_val = 1
        except ValueError:
            st.warning(f"Feeder {row['Comment']} / {row['Footprint']} için geçersiz değer. 1 olarak ayarlanacak.")
            feeder_val = 1
        unique_parts.at[idx, "Feeder"] = feeder_val
        # Nozzle kontrolü
        try:
            nozzle_val = int(nozzle) if nozzle.strip() != '' else 0
            if nozzle_val < 0 or nozzle_val > 6:
                st.warning(f"Nozzle {row['Comment']} / {row['Footprint']} için 0 ile 6 arasında olmalı.")
                nozzle_val = 0
        except ValueError:
            st.warning(f"Nozzle {row['Comment']} / {row['Footprint']} için geçersiz değer. 0 olarak ayarlanacak.")
            nozzle_val = 0
        unique_parts.at[idx, "Nozzle"] = nozzle_val
        # Pick Height
        try:
            pick_val = float(pick_height) if pick_height.strip() != "" else 0.0
            if pick_val < -15 or pick_val > 15:
                st.warning(f"Pick Height {row['Comment']} / {row['Footprint']} için -15 ile +15 arasında olmalı.")
                pick_val = 0.0
        except ValueError:
            st.warning(f"Pick Height {row['Comment']} / {row['Footprint']} için geçersiz değer. 0.0 olarak ayarlanacak.")
            pick_val = 0.0
        unique_parts.at[idx, "Pick Height"] = pick_val
        # Place Height
        try:
            place_val = float(place_height) if place_height.strip() != "" else 0.0
            if place_val < -15 or place_val > 15:
                st.warning(f"Place Height {row['Comment']} / {row['Footprint']} için -15 ile +15 arasında olmalı.")
                place_val = 0.0
        except ValueError:
            st.warning(f"Place Height {row['Comment']} / {row['Footprint']} için geçersiz değer. 0.0 olarak ayarlanacak.")
            place_val = 0.0
        unique_parts.at[idx, "Place Height"] = place_val
        # Move Speed
        try:
            move_val = int(move_speed) if move_speed.strip() != "" else 100
            if move_val < 5 or move_val > 100:
                st.warning(f"Move Speed {row['Comment']} / {row['Footprint']} için 5 ile 100 arasında olmalı.")
                move_val = 100
        except ValueError:
            st.warning(f"Move Speed {row['Comment']} / {row['Footprint']} için geçersiz değer. 100 olarak ayarlanacak.")
            move_val = 100
        unique_parts.at[idx, "Move Speed"] = move_val
        # Mode
        try:
            mode_val = int(mode) if mode.strip() != "" else 1
            if mode_val < 1 or mode_val > 4:
                st.warning(f"Mode {row['Comment']} / {row['Footprint']} için 1 ile 4 arasında olmalı.")
                mode_val = 1
        except ValueError:
            st.warning(f"Mode {row['Comment']} / {row['Footprint']} için geçersiz değer. 1 olarak ayarlanacak.")
            mode_val = 1
        unique_parts.at[idx, "Mode"] = mode_val
        # Skip
        try:
            skip_val = int(skip) if skip.strip() != "" else 0
            if skip_val not in [0, 1]:
                st.warning(f"Skip {row['Comment']} / {row['Footprint']} için 0 veya 1 olmalı.")
                skip_val = 0
        except ValueError:
            st.warning(f"Skip {row['Comment']} / {row['Footprint']} için geçersiz değer. 0 olarak ayarlanacak.")
            skip_val = 0
        unique_parts.at[idx, "Skip"] = skip_val
    # --- NOZZLE DEĞİŞİMİ FORMU ---
    nozzle_change_info = {}
    nozzle_3_exists = (unique_parts['Nozzle'] == 3).any()
    nozzle_4_exists = (unique_parts['Nozzle'] == 4).any()
    if nozzle_3_exists:
        st.subheader("Nozzle 3 için değişim bilgisi")
        nozzle3_with = st.selectbox("Hangi nozzle ile değişecek?", [1, 2], key="noz3with")
        nozzle3_drop = st.selectbox("Nereye bırakacak?", [1, 2, 3], key="noz3drop")
        nozzle3_pick = st.selectbox("Nereden alacak?", [1, 2, 3], key="noz3pick")
        nozzle_change_info[3] = {"with": nozzle3_with, "drop": nozzle3_drop, "pick": nozzle3_pick}
    if nozzle_4_exists:
        st.subheader("Nozzle 4 için değişim bilgisi")
        nozzle4_with = st.selectbox("Hangi nozzle ile değişecek?", [1, 2], key="noz4with")
        nozzle4_drop = st.selectbox("Nereye bırakacak?", [1, 2, 3], key="noz4drop")
        nozzle4_pick = st.selectbox("Nereden alacak?", [1, 2, 3], key="noz4pick")
        nozzle_change_info[4] = {"with": nozzle4_with, "drop": nozzle4_drop, "pick": nozzle4_pick}

    if st.button("Çıktı CSV'si Oluştur ve İndir"):
        merged = df.merge(unique_parts, on=["Comment", "Footprint"], how="left")
        # NOZZLE SIRALAMA
        def nozzle_sort_key(row):
            try:
                n = int(row['Nozzle'])
            except:
                n = 99
            if n in [0, 1, 2]:
                return n
            elif n == 3:
                return 10
            elif n == 4:
                return 20
            else:
                return 99
        merged = merged.sort_values(by="Nozzle", key=lambda col: col.apply(lambda x: nozzle_sort_key({'Nozzle': x})))
        # --- SAYILARI GÜNCELLEMEDEN ÖNCE HESAPLA ---
        nozzle_012_count = (merged["Nozzle"].astype(int).isin([0,1,2])).sum()
        nozzle_3_count = (merged["Nozzle"].astype(int) == 3).sum()
        # NOZZLE DEĞİŞİMİ VARSA, NOZZLE DEĞERİNİ GÜNCELLE
        for nozzle_num in [3, 4]:
            if nozzle_num in nozzle_change_info:
                with_val = nozzle_change_info[nozzle_num]["with"]
                merged.loc[merged["Nozzle"].astype(int) == nozzle_num, "Nozzle"] = with_val
        # Sütunları kullanıcı başlığına göre sırala
        merged = merged[[
            designator_col, "Comment", "Footprint", x_col, y_col, "Rotation", "Nozzle", "Feeder", "Move Speed", "Pick Height", "Place Height", "Mode", "Skip"
        ]]
        # Sütun adlarını başlıkla eşleştir
        merged.columns = [
            "Designator", "Comment", "Footprint", "Mid X(mm)", "Mid Y(mm) ", "Rotation", "Head ", "FeederNo", "Mount Speed(%)", "Pick Height(mm)", "Place Height(mm)", "Mode", "Skip"
        ]
        # Üst başlık ve ayırıcı satırları ekle
        header_lines = [
            ["NEODEN","YY1","P&P FILE","","","","","","","","","","",""],
            ["" for _ in range(14)],
            ["PanelizedPCB","UnitLength","0","UnitWidth","0","Rows","1","Columns","1","","","","",""],
            ["" for _ in range(14)],
            ["Fiducial","1-X","0","1-Y","0","OverallOffsetX","0","OverallOffsetY","0","","","","",""],
            ["" for _ in range(14)],
        ]
        # NOZZLECHANGE SATIRLARI
        nozzlechange_lines = []
        for i in range(4):
            if i == 0 and 3 in nozzle_change_info:
                info = nozzle_change_info[3]
                before_component_3 = nozzle_012_count + 1
                nozzlechange_lines.append([
                    "NozzleChange","ON","BeforeComponent",str(before_component_3),f"Head{info['with']}","Drop",f"Station{info['drop']}","PickUp",f"Station{info['pick']}" ,"","","","",""
                ])
            elif i == 1 and 4 in nozzle_change_info:
                info = nozzle_change_info[4]
                before_component_4 = nozzle_012_count + nozzle_3_count + 1
                nozzlechange_lines.append([
                    "NozzleChange","ON","BeforeComponent",str(before_component_4),f"Head{info['with']}","Drop",f"Station{info['drop']}","PickUp",f"Station{info['pick']}" ,"","","","",""
                ])
            else:
                nozzlechange_lines.append([
                    "NozzleChange","OFF","BeforeComponent","1","Head1","Drop","Station1","PickUp","Station1","","","","",""
                ])
        header_lines += nozzlechange_lines
        header_lines += [["" for _ in range(14)], ["Designator","Comment","Footprint","Mid X(mm)","Mid Y(mm) ","Rotation","Head ","FeederNo","Mount Speed(%)","Pick Height(mm)","Place Height(mm)","Mode","Skip"]]
        output = io.StringIO()
        import csv
        writer = csv.writer(output)
        for line in header_lines:
            writer.writerow(line)
        merged.to_csv(output, index=False, header=False)
        st.download_button(
            label="Çıktı CSV'sini İndir",
            data=output.getvalue(),
            file_name="smd_dizgi_cikti.csv",
            mime="text/csv"
        ) 