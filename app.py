import streamlit as st
import pandas as pd
import re
import json
import os

# Konfiguracja strony
st.set_page_config(page_title="Menadżer Cenówek", page_icon="🏷️", layout="wide")

# --- SUROWY, CZYTELNY WYGLĄD ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stDataEditor"] { border: 1px solid #c0c0c0; border-radius: 4px; }
    </style>
""", unsafe_allow_html=True)

st.title("🏷️ Menadżer Cenówek")

BACKUP_FILE = 'kopia_zapasowa.json'

# --- PRZYWRACANIE SESJI Z PLIKU ---
if 'df_wyniki' not in st.session_state:
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                dane = json.load(f)
            if dane:
                st.session_state['df_wyniki'] = pd.DataFrame(dane).sort_values(by="Departament")
        except Exception:
            pass

# --- SILNIK PARSUJĄCY ---
def parse_text(raw_text):
    full_text = re.sub(r'\s+', ' ', raw_text).strip()
    full_text = re.sub(r'Departament SKU SKUDesc.*?ean code', '', full_text, flags=re.IGNORECASE)
    full_text = re.sub(r'GAZETKA P\d+ \d{2}\.\d{2}-\d{2}\.\d{2}', '', full_text, flags=re.IGNORECASE)
    
    pattern = r'\b(\d{3})\b\s+([A-Z\s&/()]+?)\s+(\d{4,8})\s+(.*?)((?=\b\d{3}\b\s+[A-Z\s&/()]+?\s*\d{4,8}\b)|$)'
    matches = re.finditer(pattern, full_text)
    katalog = {}
    
    for match in matches:
        kod_dzialu = match.group(1).strip()
        nazwa_dzialu = match.group(2).strip()
        departament = f"{kod_dzialu} {nazwa_dzialu}"
        sku = match.group(3).strip()
        reszta_tekstu = match.group(4).strip()
        
        reg_price_match = re.search(r'(\d+[.,]\d{2})\s*zł', reszta_tekstu, re.IGNORECASE)
        if not reg_price_match: continue
            
        nazwa = reszta_tekstu[:reg_price_match.start()].strip()
        cena_reg_str = reg_price_match.group(1)
        reszta_po_reg = reszta_tekstu[reg_price_match.end():].strip()
        
        eans = re.findall(r'\*?\b(\d{8,14})\b\*?', reszta_po_reg)
        ean = "BRAK_EAN"
        for e in reversed(eans): 
            if e and e != '#ARG!':
                ean = e
                break 
                
        mtb = re.sub(r'\*?\b\d{8,14}\b\*?', '', reszta_po_reg).replace('#ARG!', '').strip()
        cena_reg_float = float(cena_reg_str.replace(',', '.'))
        cena_reg_format = "{:.2f}".format(cena_reg_float).replace('.', ',')
        
        typ, cena_promo_format, ilosc_sztuk = 'S', cena_reg_format, '1'
        promo_match = re.search(r'(\d+(?:[.,]\d{1,2})?)\s*(?:zł|pln)?\s*(?:/\s*szt\.?)?\s*przy\s*zak\S*\s*(\d+)', mtb, re.IGNORECASE)
        x_y_match = re.search(r'(\d+)\s*\+\s*(\d+)', mtb)
        simple_price = re.search(r'(\d+(?:[.,]\d{1,2})?)\s*zł', mtb, re.IGNORECASE)
        
        if promo_match:
            typ = 'P'
            cena_promo_format = "{:.2f}".format(float(promo_match.group(1).replace(',', '.')) * int(promo_match.group(2))).replace('.', ',')
            ilosc_sztuk = f"{promo_match.group(2)} szt."
        elif x_y_match:
            typ = 'P'
            ilosc_sztuk = f"{int(x_y_match.group(1)) + int(x_y_match.group(2))} szt."
            cena_promo_format = "{:.2f}".format(cena_reg_float * int(x_y_match.group(1))).replace('.', ',')
        elif simple_price:
            typ = 'P'
            cena_promo_format = "{:.2f}".format(float(simple_price.group(1).replace(',', '.'))).replace('.', ',')
            ilosc_sztuk = 'Wielosztuka'
                
        katalog[sku] = {'Departament': departament, 'Nazwa': nazwa, 'Stara_Cena': cena_reg_format, 'Nowa_Cena': cena_promo_format, 'Mechanizm': ilosc_sztuk, 'EAN': ean, 'Typ': typ}
    return katalog

# --- ZAKŁADKI NAWIGACYJNE ---
tab1, tab2 = st.tabs(["📋 LISTA ZMIAN CEN", "🏷️ AWARYJNE CENÓWKI"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        stara_text = st.text_area("📄 Tekst STAREJ gazetki:", height=120)
    with col2:
        nowa_text = st.text_area("📄 Tekst NOWEJ gazetki:", height=120)

    if st.button("🚀 PRZETWÓRZ I PORÓWNAJ", use_container_width=True):
        if stara_text and nowa_text:
            stara_baza = parse_text(stara_text)
            nowa_baza = parse_text(nowa_text)
            wyniki = []
            
            def norm_mech(m):
                m_str = str(m).lower()
                if 'wielo' in m_str: return 'w'
                nums = re.search(r'\d+', m_str)
                return nums.group() if nums else '1'

            for sku, nowa_dane in nowa_baza.items():
                if sku not in stara_baza:
                    status = "NOWA PROMOCJA"
                else:
                    stara = stara_baza[sku]
                    nowa = nowa_dane
                    czy_cena_sie_zmienila = (
                        stara['Nowa_Cena'] != nowa['Nowa_Cena'] or
                        stara['Stara_Cena'] != nowa['Stara_Cena'] or
                        norm_mech(stara['Mechanizm']) != norm_mech(nowa['Mechanizm'])
                    )
                    status = "ZMIANA CENY" if czy_cena_sie_zmienila else "PRZEDŁUŻONA PROMOCJA"
                
                wyniki.append({"🖨️ Do druku": True, "Status": status, "Departament": nowa_dane['Departament'], "SKU": sku, "Nazwa": nowa_dane['Nazwa'], "Stara Cena": nowa_dane['Stara_Cena'], "Nowa Cena": nowa_dane['Nowa_Cena'], "Ilość/Mechanizm": nowa_dane['Mechanizm'], "EAN": nowa_dane['EAN']})
            
            for sku, stara_dane in stara_baza.items():
                if sku not in nowa_baza:
                    wyniki.append({"🖨️ Do druku": True, "Status": "KONIEC PROMOCJI", "Departament": stara_dane['Departament'], "SKU": sku, "Nazwa": stara_dane['Nazwa'], "Stara Cena": stara_dane['Stara_Cena'], "Nowa Cena": "-", "Ilość/Mechanizm": "-", "EAN": stara_dane['EAN']})
            
            st.session_state['df_wyniki'] = pd.DataFrame(wyniki).sort_values(by="Departament")
            with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
                json.dump(wyniki, f, ensure_ascii=False, indent=4)
                
            st.rerun()

    if 'df_wyniki' in st.session_state and not st.session_state['df_wyniki'].empty:
        st.divider()
        df = st.session_state['df_wyniki']
        
        col_dash1, col_dash2 = st.columns([4, 1])
        with col_dash1:
            st.subheader("🎯 Panel roboczy")
        with col_dash2:
            if st.button("🗑️ Zakończ pracę", use_container_width=True, key="clear_btn"):
                if os.path.exists(BACKUP_FILE):
                    os.remove(BACKUP_FILE)
                if 'edytowany_df' in st.session_state:
                    del st.session_state['edytowany_df']
                del st.session_state['df_wyniki']
                st.rerun()
        
        nowosci_cnt = len(df[df['Status'] == 'NOWA PROMOCJA'])
        zmiany_cnt = len(df[df['Status'] == 'ZMIANA CENY'])
        przedluzone_cnt = len(df[df['Status'] == 'PRZEDŁUŻONA PROMOCJA'])
        koniec_cnt = len(df[df['Status'] == 'KONIEC PROMOCJI'])
        
        st.markdown(f"""
        <div style="display: flex; gap: 15px; margin-bottom: 25px;">
            <div style="flex: 1; background-color: #d4edda; border-radius: 4px; padding: 15px; text-align: center; color: #155724; border: 1px solid #c3e6cb;">
                <div style="font-size: 14px; text-transform: uppercase; font-weight: bold; margin-bottom: 5px;">🟢 Nowa Promocja</div>
                <div style="font-size: 32px; font-weight: bold;">{nowosci_cnt}</div>
            </div>
            <div style="flex: 1; background-color: #fff3cd; border-radius: 4px; padding: 15px; text-align: center; color: #856404; border: 1px solid #ffeeba;">
                <div style="font-size: 14px; text-transform: uppercase; font-weight: bold; margin-bottom: 5px;">🟡 Zmiany Cen</div>
                <div style="font-size: 32px; font-weight: bold;">{zmiany_cnt}</div>
            </div>
            <div style="flex: 1; background-color: #e2d9f3; border-radius: 4px; padding: 15px; text-align: center; color: #4a148c; border: 1px solid #d1c4e9;">
                <div style="font-size: 14px; text-transform: uppercase; font-weight: bold; margin-bottom: 5px;">🟣 Przedłużone</div>
                <div style="font-size: 32px; font-weight: bold;">{przedluzone_cnt}</div>
            </div>
            <div style="flex: 1; background-color: #f8d7da; border-radius: 4px; padding: 15px; text-align: center; color: #721c24; border: 1px solid #f5c6cb;">
                <div style="font-size: 14px; text-transform: uppercase; font-weight: bold; margin-bottom: 5px;">🔴 Koniec Prom.</div>
                <div style="font-size: 32px; font-weight: bold;">{koniec_cnt}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        widok = st.radio("Wybierz widok roboczy:", ["📋 WSZYSTKIE", "🟢 TYLKO NOWE PROMOCJE", "🟡 TYLKO ZMIANY CEN", "🟣 TYLKO PRZEDŁUŻONE", "🔴 TYLKO KONIEC PROMOCJI"], horizontal=True)
        
        df_filtered = df.copy()
        if widok == "🟢 TYLKO NOWE PROMOCJE": df_filtered = df_filtered[df_filtered['Status'] == 'NOWA PROMOCJA']
        elif widok == "🟡 TYLKO ZMIANY CEN": df_filtered = df_filtered[df_filtered['Status'] == 'ZMIANA CENY']
        elif widok == "🟣 TYLKO PRZEDŁUŻONE": df_filtered = df_filtered[df_filtered['Status'] == 'PRZEDŁUŻONA PROMOCJA']
        elif widok == "🔴 TYLKO KONIEC PROMOCJI": df_filtered = df_filtered[df_filtered['Status'] == 'KONIEC PROMOCJI']

        edytowany_df = st.data_editor(
            df_filtered,
            hide_index=True,
            use_container_width=True,
            column_config={
                "🖨️ Do druku": st.column_config.CheckboxColumn(required=True),
                "EAN": None, 
                "Departament": st.column_config.TextColumn(width="medium"),
                "Nazwa": st.column_config.TextColumn(width="large")
            }
        )
        
        st.session_state['edytowany_df'] = edytowany_df
        
        do_druku_df = edytowany_df[edytowany_df["🖨️ Do druku"] == True]
        if not do_druku_df.empty:
            html_content = f"""
            <!DOCTYPE html>
            <html lang="pl">
            <head>
                <meta charset="UTF-8">
                <title>Lista Zmian Cen Dealz</title>
                <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
                <style>
                    @page {{ size: A4 portrait; margin: 8mm; }}
                    * {{ box-sizing: border-box; }}
                    body {{ font-family: sans-serif; margin: 0; padding: 0; font-size: 8pt; background-color: white; }}
                    .container {{ width: 100%; max-width: 190mm; margin: 0 auto; }}
                    .departament-header {{ color: #444; font-size: 10pt; font-weight: bold; margin-top: 10px; border-bottom: 1.5px solid #ccc; text-transform: uppercase; padding-bottom: 2px; page-break-after: avoid; }}
                    .product-row {{ display: flex; align-items: center; border-bottom: 1px solid #eee; padding: 4px 0; page-break-inside: avoid; width: 100%; }}
                    .col-sku {{ width: 25%; padding-right: 5px; }}
                    .col-nazwa {{ width: 55%; padding: 0 5px; }}
                    .col-ceny {{ width: 20%; display: flex; flex-direction: column; align-items: flex-end; justify-content: center; padding-right: 5px; }}
                    .sku-text {{ font-size: 8pt; font-weight: bold; margin-bottom: 2px; }}
                    .status-label {{ font-size: 6pt; color: #0056b3; font-weight: bold; text-transform: uppercase; margin-bottom: 1px; }}
                    .nazwa-text {{ font-size: 8pt; font-weight: bold; color: #222; line-height: 1.1; }}
                    .cena-stara {{ text-decoration: line-through; color: #888; font-size: 7pt; margin-bottom: 1px; }}
                    .cena-nowa {{ font-size: 11pt; font-weight: bold; color: #000; }}
                    .mechanizm {{ font-size: 7pt; font-weight: bold; background: #f0f0f0; padding: 1px 4px; border-radius: 3px; border: 1px solid #ccc; margin-top: 2px; text-align: center; }}
                    svg {{ max-height: 20px; width: 100%; object-fit: contain; display: block; margin-top: 2px; }}
                </style>
            </head>
            <body>
                <div class="container">
            """
            curr_dept = ""
            js_barcode_calls = ""
            for _, row in do_druku_df.iterrows():
                if row['Departament'] != curr_dept:
                    html_content += f"<div class='departament-header'>{row['Departament']}</div>"
                    curr_dept = row['Departament']
                
                ean, sku = str(row['EAN']), str(row['SKU'])
                barcode_html = f"<svg id='b{sku}'></svg>" if ean.isdigit() and ean != "BRAK_EAN" else "<div style='font-size:6pt;color:#ccc;margin-top:2px;'>Brak EAN</div>"
                if ean.isdigit() and ean != "BRAK_EAN":
                    js_barcode_calls += f"JsBarcode('#b{sku}', '{ean}', {{format:'CODE128',width:1.5,height:20,displayValue:false,margin:0}});"
                
                stara_cena = f"Reg: {row['Stara Cena']} zł" if row['Status'] != "NOWA PROMOCJA" else ""
                mech = f"<div class='mechanizm'>{row['Ilość/Mechanizm']}</div>" if row['Ilość/Mechanizm'] not in ["1", "-", "1 szt."] else ""
                nowa_cena_format = f"{row['Nowa Cena']} zł" if row['Nowa Cena'] != "-" else "-"
                
                html_content += f"""
                <div class='product-row'>
                    <div class='col-sku'><div class='sku-text'>{sku}</div>{barcode_html}</div>
                    <div class='col-nazwa'><div class='status-label'>{row['Status']}</div><div class='nazwa-text'>{row['Nazwa']}</div></div>
                    <div class='col-ceny'><span class='cena-stara'>{stara_cena}</span><span class='cena-nowa'>{nowa_cena_format}</span>{mech}</div>
                </div>"""
            
            html_content += f"""
                </div>
                <script>
                    window.onload = function() {{ 
                        {js_barcode_calls} 
                        setTimeout(function() {{ window.print(); }}, 600); 
                    }};
                </script>
            </body>
            </html>"""

            st.divider()
            st.download_button(
                label="💾 POBIERZ LISTĘ DO DRUKU",
                data=html_content.encode('utf-8'),
                file_name="zmiana_cen.html",
                mime="text/html",
                use_container_width=True
            )

with tab2:
    bridge_data = []
    if 'edytowany_df' in st.session_state and not st.session_state['edytowany_df'].empty:
        tabela_z_zakladki_1 = st.session_state['edytowany_df']
        tylko_zaklikane = tabela_z_zakladki_1[tabela_z_zakladki_1["🖨️ Do druku"] == True]
        df_valid = tylko_zaklikane[tylko_zaklikane['Status'].isin(['NOWA PROMOCJA', 'ZMIANA CENY', 'PRZEDŁUŻONA PROMOCJA'])]
        
        for _, row in df_valid.iterrows():
            mech = str(row['Ilość/Mechanizm'])
            
            qty_match = re.search(r'\d+', mech)
            qty_val = qty_match.group() if qty_match else "1"
            
            is_promo = True if (int(qty_val) > 1 or 'wielo' in mech.lower()) else False
            if 'wielo' in mech.lower() and int(qty_val) == 1:
                qty_val = "2"

            try: p_price = float(str(row['Nowa Cena']).replace(',', '.')) if row['Nowa Cena'] != '-' else 0
            except: p_price = 0

            try: r_price = float(str(row['Stara Cena']).replace(',', '.')) if row['Stara Cena'] != '-' else p_price
            except: r_price = p_price

            bridge_data.append({
                "type": "promo" if is_promo else "standard",
                "data": {
                    "name": str(row['Nazwa']),
                    "promoPriceTotal": p_price,
                    "regPrice": r_price,
                    "ean": str(row['EAN']).replace('BRAK_EAN', ''),
                    "promoQty": qty_val,
                    "sku": str(row['SKU'])
                }
            })

    html_head = """
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Generator Cenówek</title>
        <link href="https://fonts.googleapis.com/css2?family=Libre+Barcode+39&display=swap" rel="stylesheet">
        <style>
            body { background-color: #e0e0e0; margin: 0; font-family: Arial, sans-serif; display: flex; flex-direction: column; align-items: center; padding-bottom: 50px; }
            .controls { position: sticky; top: 0; background-color: #333; width: 100%; padding: 15px; text-align: center; box-shadow: 0 2px 10px rgba(0,0,0,0.3); z-index: 100; display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: 8px; }
            .controls button { background-color: #fff; border: none; padding: 10px 15px; font-size: 14px; cursor: pointer; border-radius: 5px; font-weight: bold; transition: 0.2s; }
            .controls button:hover { filter: brightness(0.9); }
            .btn-add { background-color: #f1f1f1; color: #333; }
            .btn-danger { background-color: #dc3545 !important; color: white; }
            .btn-warning { background-color: #ff9800 !important; color: white; }
            .btn-import-csv { background-color: #17a2b8 !important; color: white; }
            .btn-print { background-color: #4CAF50 !important; color: white; }
            .btn-bridge { background-color: #ff4081 !important; color: white; border: 2px solid #fff !important; }
            .btn-duplicate { background-color: #ffc107 !important; color: #000; }
            .search-box { padding: 9px 15px; border-radius: 5px; border: none; outline: none; width: 220px; font-size: 14px; }
            .divider { width: 2px; height: 30px; background-color: #555; margin: 0 5px; }
            .hint { width: 100%; color: #aaa; font-size: 12px; margin-top: 5px; }
            
            /* BEZSTRESOWY UKŁAD POZIOMY A4 - 12 SZTUK (3x4) BEZ PRZERW */
            .a4-page { 
                background-color: #fff; 
                width: 297mm; 
                height: 210mm; 
                margin: 20px auto; 
                box-shadow: 0 0 10px rgba(0,0,0,0.1); 
                box-sizing: border-box; 
                display: grid; 
                grid-template-columns: 75mm 75mm 75mm; 
                grid-template-rows: repeat(4, 37mm); 
                justify-content: center; 
                align-content: center;   
                gap: 0; 
                position: relative; 
            }
            .page-number { position: absolute; bottom: 5mm; right: 10mm; font-size: 12px; color: #999; }
            
            .tag-wrapper { 
                width: 75mm; 
                height: 37mm; 
                position: relative; 
                box-sizing: border-box; 
                border: 1px dashed #ccc; 
                background-color: #ffffff; 
                overflow: hidden; 
                cursor: pointer; 
            }
            .tag-wrapper.selected { outline: 2px solid #007bff; z-index: 10; }
            
            .price-tag { width: 750px; height: 370px; position: absolute; top: 0; left: 0; color: #333; transform: scale(0.37795); transform-origin: top left; pointer-events: none; }
            .price-tag > * { pointer-events: auto; } 
            [contenteditable="true"]:hover { background-color: rgba(0, 0, 0, 0.05); outline: 2px dashed #999; cursor: text; }
            [contenteditable="true"]:focus { background-color: rgba(0, 123, 255, 0.1); outline: 2px solid #007bff; cursor: text; }
            
            .meta-code { position: absolute; font-size: 16px; letter-spacing: 1px; }
            .barcode { position: absolute; font-family: 'Libre Barcode 39', cursive; font-size: 60px; line-height: 0.8; font-weight: normal; pointer-events: none; }
            .barcode-numbers { position: absolute; font-size: 15px; letter-spacing: 5px; }
            .omnibus { position: absolute; bottom: 30px; right: 30px; font-size: 13px; text-align: right; line-height: 1.2; display: flex; align-items: flex-end; gap: 15px; }
            .omnibus-text { text-align: left; }
            .omnibus-price { font-size: 16px; font-weight: bold; }
            .product-name { position: absolute; overflow: hidden; display: flex; align-items: flex-start; align-content: flex-start; flex-wrap: wrap; line-height: 0.95; }
            
            .promo .promo-amount { position: absolute; top: 15px; left: 30px; font-size: 70px; font-weight: bold; line-height: 1; color: #000; }
            .promo .promo-price-container { position: absolute; top: 85px; left: 30px; display: flex; align-items: flex-end; }
            .promo .promo-price { font-size: 120px; font-weight: bold; line-height: 0.8; color: #000; }
            .promo .promo-currency { font-size: 45px; margin-left: 5px; line-height: 1.2; }
            .promo .regular-box { position: absolute; top: 105px; right: 30px; display: flex; align-items: center; justify-content: flex-end; max-width: 350px; }
            .promo .regular-label { font-size: 14px; text-align: right; line-height: 1.1; margin-right: 15px; flex-shrink: 0; }
            .promo .regular-price { font-size: 90px; font-weight: bold; line-height: 0.8; color: #000; }
            .promo .regular-currency { font-size: 40px; margin-left: 5px; line-height: 1.2; }
            .promo .unit-price-promo { position: absolute; top: 215px; left: 30px; font-size: 18px; font-weight: bold; color: #333; }
            .promo .unit-price-regular { position: absolute; top: 215px; right: 30px; font-size: 18px; font-weight: bold; color: #333; }
            .promo .meta-code { top: 240px; left: 30px; }
            .promo .barcode { bottom: 40px; left: 30px; }
            .promo .barcode-numbers { bottom: 20px; left: 55px; }
            .promo .product-name { top: 30px; left: 260px; height: 75px; font-size: 32px; width: 460px; }
            
            .standard .meta-code { top: 240px; left: 30px; }
            .standard .barcode { bottom: 40px; left: 30px; }
            .standard .barcode-numbers { bottom: 20px; left: 55px; }
            .standard .std-price-container { position: absolute; top: 80px; right: 30px; display: flex; align-items: flex-end; }
            .standard .std-price { font-size: 150px; font-weight: bold; line-height: 0.8; }
            .standard .std-currency { font-size: 60px; margin-left: 5px; line-height: 1.2; }
            .standard .std-unit-price { position: absolute; top: 240px; right: 30px; font-size: 24px; font-weight: bold; color: #333; }
            .standard .product-name { top: 35px; left: 30px; height: 100px; font-size: 38px; width: 450px; } 
            
            /* BEZSTRESOWY UKŁAD POZIOMY (LANDSCAPE) - 12 CENÓWEK */
            @media print {
                @page { size: A4 landscape; margin: 0 !important; } 
                body { background-color: #fff; margin: 0 !important; padding: 0 !important; }
                .controls, #templates, .no-print, .page-number { display: none !important; }
                
                .a4-page { 
                    width: 297mm !important; 
                    height: 210mm !important; 
                    margin: 0 !important; 
                    /* Ponad 3 centymetry luzu z każdej strony! */
                    padding: 31mm 36mm !important; 
                    box-sizing: border-box !important; 
                    display: grid !important; 
                    grid-template-columns: 75mm 75mm 75mm !important; /* 3 kolumny */
                    grid-auto-rows: 37mm !important; /* 4 rzędy */
                    gap: 0 !important;
                    page-break-after: always !important; 
                    box-shadow: none !important;
                    overflow: hidden !important;
                    zoom: 1 !important;
                }
                .a4-page:last-child { page-break-after: auto !important; }
                
                .tag-wrapper { 
                    width: 75mm !important; 
                    height: 37mm !important; 
                    margin: 0 !important;
                    border: 1px dashed #ccc !important; 
                    box-sizing: border-box !important; 
                    page-break-inside: avoid !important; 
                    float: none !important;
                } 
                .tag-wrapper.selected { outline: none !important; }
                [contenteditable="true"]:hover, [contenteditable="true"]:focus { outline: none; background-color: transparent; }
            }
        </style>
    </head>
    <body>
        <div id="templates" style="display: none;">
            <div class="tag-wrapper" id="tpl-promo">
                <div class="price-tag promo">
                    <div class="promo-amount" contenteditable="true">2 za</div>
                    <div class="promo-price-container">
                        <div class="promo-price" contenteditable="true">24</div>
                        <div class="promo-currency" contenteditable="true">PLN</div>
                    </div>
                    <div class="unit-price-promo" contenteditable="true">12,00 PLN za 1szt</div>
                    <div class="meta-code" contenteditable="true"><span class="code-prefix">SKU</span>-<span class="auto-date">XX/XX/XXXX</span>-<span class="code-suffix">R</span></div>
                    <div class="barcode">*0000000000000*</div>
                    <div class="barcode-numbers" contenteditable="true">0000000000000</div>
                    <div class="product-name" contenteditable="true">Wpisz Nazwę</div>
                    
                    <div class="regular-box">
                        <div class="regular-label" contenteditable="true">cena<br>regularna</div>
                        <div class="regular-price" contenteditable="true">16</div>
                        <div class="regular-currency" contenteditable="true">PLN</div>
                    </div>
                    
                    <div class="unit-price-regular" contenteditable="true">16,00 PLN za 1szt</div>
                    <div class="omnibus" contenteditable="true">
                        <div class="omnibus-text">najniższa cena<br>z 30 dni przed<br>obniżką</div>
                        <div class="omnibus-price" contenteditable="true">16 PLN</div>
                    </div>
                </div>
            </div>
            <div class="tag-wrapper" id="tpl-standard">
                <div class="price-tag standard">
                    <div class="product-name" contenteditable="true">Nazwa Produktu</div>
                    <div class="meta-code" contenteditable="true"><span class="code-prefix">SKU</span>-<span class="auto-date">XX/XX/XXXX</span>-<span class="code-suffix">R</span></div>
                    <div class="barcode">*0000000000000*</div>
                    <div class="barcode-numbers" contenteditable="true">0000000000000</div>
                    
                    <div class="std-price-container">
                        <div class="std-price" contenteditable="true">0</div>
                        <div class="std-currency" contenteditable="true">PLN</div>
                    </div>
                    
                    <div class="std-unit-price" contenteditable="true">0,00 PLN za 1szt</div>
                    <div class="omnibus" contenteditable="true">
                        <div class="omnibus-text">najniższa cena<br>z 30 dni przed<br>obniżką</div>
                        <div class="omnibus-price" contenteditable="true">0 PLN</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="controls no-print">
            <button class="btn-add" onclick="addTag('standard')">➕ Standard</button>
            <button class="btn-add" onclick="addTag('promo')">➕ Promocja</button>
            <div class="divider"></div>
            <button class="btn-bridge" onclick="importFromBridge()">📥 Pobierz z Listy Zmian</button>
            <div class="divider"></div>
            <button class="btn-duplicate" onclick="duplicateSelected()">📋 Powiel</button>
            <button class="btn-danger" onclick="deleteSelected()">🗑️ Usuń</button>
            <button class="btn-warning" onclick="clearAll()">💥 Wyczyść</button>
            <div class="divider"></div>
            <input type="file" id="csv-upload" accept=".csv" style="display: none;" onchange="handleCSV(event)">
            <button class="btn-import-csv" onclick="document.getElementById('csv-upload').click()">📂 CSV</button>
            <button class="btn-print" onclick="downloadHTML()">🖨️ Pobierz do Druku (HTML)</button>
            <div class="divider"></div>
            <input type="text" id="searchInput" class="search-box" placeholder="🔍 Szukaj..." oninput="filterTags()">
            <div class="hint">⚠️ <b>Zanim wydrukujesz:</b> Upewnij się, że w oknie drukarki <b>Skala = 100%</b>. | Z wciśniętym <b>CTRL</b> zaznaczasz kilka cenówek. <b>ALT + [ ]</b> pomniejsza tekst.</div>
        </div>
        <div id="pages-container"></div>
        <script>
    """
    
    html_bridge = f"window.BRIDGE_DATA = {json.dumps(bridge_data)};"
    
    html_tail = """
            const MathVars = { TAGS_PER_PAGE: 12 };

            function importFromBridge() {
                if (!window.BRIDGE_DATA || window.BRIDGE_DATA.length === 0) {
                    alert("Brak danych! Przejdź do zakładki 'LISTA ZMIAN CEN', przetwórz gazetkę i upewnij się, że z lewej strony są zaznaczone checkboxy 'Do druku'!");
                    return;
                }
                if (confirm("Czy chcesz automatycznie wygenerować " + window.BRIDGE_DATA.length + " cenówek na podstawie dzisiejszej gazetki?")) {
                    window.BRIDGE_DATA.forEach(item => {
                        addTag(item.type, true, item.data);
                    });
                    autoFitAll();
                }
            }

            function downloadHTML() {
                const htmlContent = "<!DOCTYPE html>\\n<html lang='pl'>\\n<head>\\n" + document.head.innerHTML + "\\n</head>\\n<body>\\n" + document.body.innerHTML + "\\n</body>\\n</html>";
                const blob = new Blob([htmlContent], { type: 'text/html' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = "Awaryjne_Cenowki_Dealz.html";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                alert("Zapisano! Kliknij w pobrany plik na dole ekranu, a okno drukowania otworzy się automatycznie.");
            }

            function saveState() {
                try {
                    const container = document.getElementById('pages-container');
                    const tempClone = container.cloneNode(true);
                    tempClone.querySelectorAll('.tag-wrapper, .a4-page').forEach(el => {
                        el.style.display = '';
                        el.classList.remove('selected');
                    });
                    localStorage.setItem('mtb_tags_saved', tempClone.innerHTML);
                } catch (e) {}
            }

            function loadState() {
                const saved = localStorage.getItem('mtb_tags_saved');
                if (saved) {
                    document.getElementById('pages-container').innerHTML = saved;
                }
            }

            window.addEventListener('DOMContentLoaded', loadState);

            window.addEventListener('beforeprint', function() {
                const searchInput = document.getElementById('searchInput');
                if(searchInput.value !== '') {
                    searchInput.value = '';
                    filterTags(); 
                }
                document.querySelectorAll('.tag-wrapper.selected').forEach(t => t.classList.remove('selected'));
            });

            document.addEventListener('paste', function(e) {
                if (e.target.isContentEditable) {
                    e.preventDefault();
                    let text = (e.originalEvent || e).clipboardData.getData('text/plain');
                    const selection = window.getSelection();
                    if (!selection.rangeCount) return;
                    selection.deleteFromDocument();
                    selection.getRangeAt(0).insertNode(document.createTextNode(text));
                    selection.collapseToEnd();
                }
            });

            function applyCurrentDate(element) {
                const dzisiaj = new Date();
                const formatDaty = String(dzisiaj.getDate()).padStart(2, '0') + '/' + String(dzisiaj.getMonth() + 1).padStart(2, '0') + '/' + dzisiaj.getFullYear();
                element.querySelectorAll('.auto-date').forEach(el => el.textContent = formatDaty);
            }

            function formatCleanPrice(num) {
                if (isNaN(num)) return "0";
                let str = Number(num).toFixed(2).replace('.', ',');
                if (str.endsWith(',00')) return str.replace(',00', '');
                return str;
            }

            function recalculateMath(tag) {
                if (!tag) return;
                const isPromo = tag.classList.contains('promo');

                const nameText = (tag.querySelector('.product-name').textContent || "").toLowerCase().replace(',', '.');
                const capMatch = nameText.match(/(\\d+(?:\\.\\d+)?)\\s*(ml|l|g|kg)\\b/i);

                if (isPromo) {
                    const qtyMatch = (tag.querySelector('.promo-amount').textContent || "").match(/\\d+/);
                    const qty = qtyMatch ? parseInt(qtyMatch[0]) : 1;
                    const pCurr = (tag.querySelector('.promo-currency').textContent || "PLN").trim();
                    const pText = (tag.querySelector('.promo-price').textContent || "0").replace(/\\s/g, '').replace(',', '.');
                    const pPrice = parseFloat(pText);
                    
                    if (!isNaN(pPrice) && qty > 0) {
                        let pricePerPiece = pPrice / qty;
                        let calcPrice = pricePerPiece;
                        let unitStr = "1szt";

                        if (capMatch) {
                            let amount = parseFloat(capMatch[1]);
                            let u = capMatch[2];
                            if (amount > 0) {
                                if (u === 'ml') { calcPrice = (pricePerPiece / amount) * 100; unitStr = "100ml"; }
                                else if (u === 'l') { calcPrice = (pricePerPiece / amount) * 1; unitStr = "1L"; }
                                else if (u === 'g') { calcPrice = (pricePerPiece / amount) * 100; unitStr = "100g"; }
                                else if (u === 'kg') { calcPrice = (pricePerPiece / amount) * 1; unitStr = "1kg"; }
                            }
                        }
                        tag.querySelector('.unit-price-promo').textContent = calcPrice.toFixed(2).replace('.', ',') + " " + pCurr + " za " + unitStr;
                    }

                    const rCurr = (tag.querySelector('.regular-currency').textContent || "PLN").trim();
                    const rText = (tag.querySelector('.regular-price').textContent || "0").replace(/\\s/g, '').replace(',', '.');
                    const rPrice = parseFloat(rText);

                    if (!isNaN(rPrice)) {
                        let calcReg = rPrice;
                        let unitStrReg = "1szt";
                        
                        if (capMatch) {
                            let amount = parseFloat(capMatch[1]);
                            let u = capMatch[2];
                            if (amount > 0) {
                                if (u === 'ml') { calcReg = (rPrice / amount) * 100; unitStrReg = "100ml"; }
                                else if (u === 'l') { calcReg = (rPrice / amount) * 1; unitStrReg = "1L"; }
                                else if (u === 'g') { calcReg = (rPrice / amount) * 100; unitStrReg = "100g"; }
                                else if (u === 'kg') { calcReg = (rPrice / amount) * 1; unitStrReg = "1kg"; }
                            }
                        }
                        tag.querySelector('.unit-price-regular').textContent = calcReg.toFixed(2).replace('.', ',') + " " + rCurr + " za " + unitStrReg;
                        tag.querySelector('.omnibus-price').textContent = rPrice.toFixed(2).replace('.', ',') + " " + rCurr;
                    }
                } else {
                    const curr = (tag.querySelector('.std-currency').textContent || "PLN").trim();
                    const sText = (tag.querySelector('.std-price').textContent || "0").replace(/\\s/g, '').replace(',', '.');
                    const sPrice = parseFloat(sText);

                    if (!isNaN(sPrice)) {
                        let calcStd = sPrice;
                        let unitStrStd = "1szt";
                        
                        if (capMatch) {
                            let amount = parseFloat(capMatch[1]);
                            let u = capMatch[2];
                            if (amount > 0) {
                                if (u === 'ml') { calcStd = (sPrice / amount) * 100; unitStrStd = "100ml"; }
                                else if (u === 'l') { calcStd = (sPrice / amount) * 1; unitStrStd = "1L"; }
                                else if (u === 'g') { calcStd = (sPrice / amount) * 100; unitStrStd = "100g"; }
                                else if (u === 'kg') { calcStd = (sPrice / amount) * 1; unitStrStd = "1kg"; }
                            }
                        }
                        tag.querySelector('.std-unit-price').textContent = calcStd.toFixed(2).replace('.', ',') + " " + curr + " za " + unitStrStd;
                        tag.querySelector('.omnibus-price').textContent = sPrice.toFixed(2).replace('.', ',') + " " + curr;
                    }
                }
            }

            function autoFitAll() {
                setTimeout(() => {
                    document.querySelectorAll('.price-tag').forEach(tag => {
                        const nameEl = tag.querySelector('.product-name');
                        if (!nameEl || nameEl.offsetWidth === 0 || nameEl.offsetHeight === 0) return;
                        
                        const isPromo = tag.classList.contains('promo');
                        if (!isPromo) {
                            const priceContainer = tag.querySelector('.std-price-container');
                            if (priceContainer) {
                                const priceWidth = priceContainer.offsetWidth;
                                const maxSafeWidth = 750 - 30 - 40 - priceWidth; 
                                nameEl.style.width = maxSafeWidth + 'px';
                            }
                        }

                        let max = isPromo ? 32 : 38;
                        let min = 10; 
                        nameEl.style.fontSize = max + 'px';
                        
                        while (nameEl.scrollHeight > nameEl.clientHeight && max > min) {
                            max -= 0.5;
                            nameEl.style.fontSize = max + 'px';
                        }
                    });
                    saveState(); 
                }, 50);
            }

            function getAvailablePage() {
                const container = document.getElementById('pages-container');
                let pages = container.querySelectorAll('.a4-page');
                let lastPage = pages[pages.length - 1];

                if (!lastPage || lastPage.querySelectorAll('.tag-wrapper').length >= MathVars.TAGS_PER_PAGE) {
                    lastPage = document.createElement('div');
                    lastPage.className = 'a4-page';
                    const pageNum = document.createElement('div');
                    pageNum.className = 'page-number';
                    pageNum.textContent = `Strona ${pages.length + 1}`;
                    lastPage.appendChild(pageNum);
                    container.appendChild(lastPage);
                }
                return lastPage;
            }

            function addTag(type, isInitial = false, customData = null) {
                const template = document.getElementById('tpl-' + type);
                if (!template) return; 

                const clone = template.cloneNode(true);
                clone.removeAttribute('id'); 
                applyCurrentDate(clone);
                
                const priceTag = clone.querySelector('.price-tag');

                if (customData) {
                    clone.querySelector('.product-name').innerHTML = customData.name;
                    clone.querySelector('.barcode-numbers').textContent = customData.ean;
                    clone.querySelector('.barcode').textContent = '*' + customData.ean + '*';
                    
                    if (customData.sku) {
                        const prefixEl = clone.querySelector('.code-prefix');
                        if (prefixEl) prefixEl.textContent = customData.sku;
                    }

                    if (type === 'promo') {
                        clone.querySelector('.promo-amount').textContent = customData.promoQty + " za";
                        clone.querySelector('.promo-price').textContent = formatCleanPrice(customData.promoPriceTotal);
                        clone.querySelector('.regular-price').textContent = formatCleanPrice(customData.regPrice);
                    } else {
                        const stdTargetPrice = (customData.promoPriceTotal && customData.promoPriceTotal > 0) ? customData.promoPriceTotal : customData.regPrice;
                        clone.querySelector('.std-price').textContent = formatCleanPrice(stdTargetPrice);
                    }
                    
                    recalculateMath(priceTag);
                }

                const page = getAvailablePage();
                page.appendChild(clone);
            }

            function handleCSV(event) {
                const file = event.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    let text = e.target.result;
                    let inQuotes = false;
                    let cleanedText = "";
                    
                    for (let i = 0; i < text.length; i++) {
                        let char = text[i];
                        if (char === '"') inQuotes = !inQuotes; 
                        if (inQuotes && (char === '\\n' || char === '\\r')) {
                            if (char === '\\n') cleanedText += " ";
                            continue; 
                        }
                        cleanedText += char;
                    }

                    const lines = cleanedText.split('\\n');
                    document.getElementById('pages-container').innerHTML = ''; 
                    
                    for (let i = 1; i < lines.length; i++) {
                        if (!lines[i].trim()) continue;
                        const cols = lines[i].split(';');
                        
                        if (cols.length >= 6) {
                            const type = cols[0] === 'P' ? 'promo' : 'standard';
                            let pVal = (cols[2] || "0").replace(/\\s/g, '').replace(',', '.');
                            let rVal = (cols[3] || "0").replace(/\\s/g, '').replace(',', '.');

                            const data = {
                                name: cols[1],
                                promoPriceTotal: parseFloat(pVal),
                                regPrice: parseFloat(rVal),
                                ean: cols[4] ? cols[4].replace(/"/g, '').trim() : "",
                                promoQty: cols[5] ? cols[5].trim() : "1",
                                sku: cols[6] ? cols[6].trim() : "SKU"
                            };
                            addTag(type, true, data);
                        }
                    }
                    autoFitAll(); 
                    event.target.value = ''; 
                };
                reader.readAsText(file, "UTF-8"); 
            }

            document.addEventListener('click', function(e) {
                const tag = e.target.closest('.tag-wrapper');
                if (e.target.isContentEditable) return; 
                if (tag && tag.closest('#templates')) return;

                if (tag) {
                    if (e.ctrlKey) {
                        tag.classList.toggle('selected');
                    } else {
                        document.querySelectorAll('.tag-wrapper').forEach(t => t.classList.remove('selected'));
                        tag.classList.add('selected');
                    }
                } else if (!e.target.closest('.controls')) {
                    document.querySelectorAll('.tag-wrapper').forEach(t => t.classList.remove('selected'));
                }
            });

            function deleteSelected() {
                const selected = document.querySelectorAll('#pages-container .tag-wrapper.selected');
                if (selected.length === 0) {
                    alert("Najpierw zaznacz cenówkę klikając w jej puste tło.");
                    return;
                }
                selected.forEach(tag => tag.remove());
                cleanEmptyPages();
                saveState();
            }

            function clearAll() { 
                if (confirm("Jesteś pewien, że chcesz usunąć wszystkie cenówki?")) { 
                    document.getElementById('pages-container').innerHTML = ''; 
                    saveState();
                } 
            }

            function cleanEmptyPages() {
                document.querySelectorAll('.a4-page').forEach(page => {
                    if (page.querySelectorAll('.tag-wrapper').length === 0) page.remove();
                });
                document.querySelectorAll('.a4-page').forEach((page, index) => {
                    const pageNumEl = page.querySelector('.page-number');
                    if (pageNumEl) pageNumEl.textContent = `Strona ${index + 1}`;
                });
            }

            document.addEventListener('keydown', function(e) {
                const el = document.activeElement;
                if (el && el.isContentEditable && e.altKey) {
                    e.preventDefault(); 
                    let style = window.getComputedStyle(el);
                    let fontSize = parseFloat(style.fontSize);
                    let transform = style.transform;
                    let tx = 0, ty = 0;
                    
                    if (transform !== 'none') {
                        let matrix = transform.match(/^matrix\\((.+)\\)$/);
                        if (matrix) {
                            let values = matrix[1].split(', ');
                            tx = parseFloat(values[4]);
                            ty = parseFloat(values[5]);
                        }
                    }

                    const step = 2; 
                    
                    if (e.key === '[') el.style.fontSize = (fontSize - step) + 'px';
                    if (e.key === ']') el.style.fontSize = (fontSize + step) + 'px';
                    if (e.key === 'ArrowUp') ty -= step;
                    if (e.key === 'ArrowDown') ty += step;
                    if (e.key === 'ArrowLeft') tx -= step;
                    if (e.key === 'ArrowRight') tx += step;

                    el.style.transform = `translate(${tx}px, ${ty}px)`;
                    saveState();
                }
            });

            document.addEventListener('input', function(e) {
                const priceTag = e.target.closest('.price-tag');
                
                if (priceTag && e.target.classList.contains('barcode-numbers')) {
                    const barcodeEl = priceTag.querySelector('.barcode');
                    if (barcodeEl) {
                        const cleanNumbers = e.target.textContent.replace(/\\s+/g, '');
                        barcodeEl.textContent = '*' + cleanNumbers + '*';
                    }
                }

                if (priceTag && (e.target.classList.contains('promo-price') || 
                                 e.target.classList.contains('regular-price') || 
                                 e.target.classList.contains('promo-amount') || 
                                 e.target.classList.contains('std-price') ||
                                 e.target.classList.contains('product-name'))) {
                    recalculateMath(priceTag);
                }

                if (e.target.classList.contains('product-name')) {
                    let el = e.target;
                    let isPromo = el.closest('.promo') !== null;
                    let max = isPromo ? 32 : 38;
                    let min = 10;
                    
                    el.style.fontSize = max + 'px';
                    while (el.scrollHeight > el.clientHeight && max > min) {
                        max -= 0.5;
                        el.style.fontSize = max + 'px';
                    }
                }
                if (e.target.isContentEditable) saveState();
            });

            function duplicateSelected() {
                const selected = document.querySelectorAll('#pages-container .tag-wrapper.selected');
                if (selected.length === 0) {
                    alert("Najpierw zaznacz cenówkę (lub kilka z wciśniętym CTRL), którą chcesz powielić.");
                    return;
                }
                
                selected.forEach(tag => {
                    const clone = tag.cloneNode(true);
                    clone.classList.remove('selected');
                    const page = getAvailablePage();
                    page.appendChild(clone);
                });
                
                saveState();
            }

            function filterTags() {
                const query = document.getElementById('searchInput').value.toLowerCase();
                const tags = document.querySelectorAll('#pages-container .tag-wrapper');
                
                tags.forEach(tag => {
                    const name = (tag.querySelector('.product-name')?.textContent || "").toLowerCase();
                    const sku = (tag.querySelector('.code-prefix')?.textContent || "").toLowerCase();
                    const ean = (tag.querySelector('.barcode-numbers')?.textContent || "").toLowerCase();
                    
                    if (name.includes(query) || sku.includes(query) || ean.includes(query)) {
                        tag.style.display = ''; 
                    } else {
                        tag.style.display = 'none'; 
                    }
                });
                
                document.querySelectorAll('#pages-container .a4-page').forEach(page => {
                    const visibleTags = Array.from(page.querySelectorAll('.tag-wrapper')).filter(t => t.style.display !== 'none');
                    if (visibleTags.length === 0) {
                        page.style.display = 'none';
                    } else {
                        page.style.display = 'grid';
                    }
                });
            }
            
            if(window.location.href.startsWith("blob:")) {
                 window.onload = function() { setTimeout(function(){ window.print(); }, 800); };
            }
        </script>
    </body>
    </html>
    """
    
    final_html = html_head + html_bridge + html_tail
    st.components.v1.html(final_html, height=850, scrolling=True)
