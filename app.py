import streamlit as st
import pandas as pd
import re
import base64

# Konfiguracja strony
st.set_page_config(page_title="Asystent Dealz", page_icon="🏷️", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    /* Delikatne ukrycie indeksu w Streamlit */
    div[data-testid="stDataEditor"] { border: 1px solid #e0e0e0; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("🏷️ Asystent Zmiany Cen")

# --- SILNIK PARSUJĄCY (BEZ ZMIAN) ---
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

# --- INTERFEJS WPROWADZANIA ---
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
        
        for sku, nowa_dane in nowa_baza.items():
            status = "NOWOŚĆ" if sku not in stara_baza else ("ZMIANA CENY" if nowa_dane != stara_baza[sku] else "BEZ ZMIAN")
            if status != "BEZ ZMIAN":
                wyniki.append({"🖨️ Do druku": True, "Status": status, "Departament": nowa_dane['Departament'], "SKU": sku, "Nazwa": nowa_dane['Nazwa'], "Stara Cena": nowa_dane['Stara_Cena'], "Nowa Cena": nowa_dane['Nowa_Cena'], "Ilość/Mechanizm": nowa_dane['Mechanizm'], "EAN": nowa_dane['EAN']})
        
        for sku, stara_dane in stara_baza.items():
            if sku not in nowa_baza:
                wyniki.append({"🖨️ Do druku": True, "Status": "KONIEC PROMOCJI", "Departament": stara_dane['Departament'], "SKU": sku, "Nazwa": stara_dane['Nazwa'], "Stara Cena": stara_dane['Stara_Cena'], "Nowa Cena": "-", "Ilość/Mechanizm": "-", "EAN": stara_dane['EAN']})
        
        st.session_state['df_wyniki'] = pd.DataFrame(wyniki).sort_values(by="Departament")

# --- CENTRUM DOWODZENIA (PULPIT) ---
if 'df_wyniki' in st.session_state and not st.session_state['df_wyniki'].empty:
    st.divider()
    df = st.session_state['df_wyniki']
    
    # 1. Pastelowe Kafelki Podsumowujące
    nowosci_cnt = len(df[df['Status'] == 'NOWOŚĆ'])
    zmiany_cnt = len(df[df['Status'] == 'ZMIANA CENY'])
    koniec_cnt = len(df[df['Status'] == 'KONIEC PROMOCJI'])
    
    st.markdown(f"""
    <div style="display: flex; gap: 15px; margin-bottom: 25px;">
        <div style="flex: 1; background-color: #d4edda; border-radius: 8px; padding: 15px; text-align: center; color: #155724; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 14px; text-transform: uppercase; font-weight: bold; margin-bottom: 5px;">🟢 Nowości</div>
            <div style="font-size: 32px; font-weight: bold;">{nowosci_cnt}</div>
        </div>
        <div style="flex: 1; background-color: #fff3cd; border-radius: 8px; padding: 15px; text-align: center; color: #856404; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 14px; text-transform: uppercase; font-weight: bold; margin-bottom: 5px;">🟡 Zmiany Cen</div>
            <div style="font-size: 32px; font-weight: bold;">{zmiany_cnt}</div>
        </div>
        <div style="flex: 1; background-color: #f8d7da; border-radius: 8px; padding: 15px; text-align: center; color: #721c24; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <div style="font-size: 14px; text-transform: uppercase; font-weight: bold; margin-bottom: 5px;">🔴 Koniec Promocji</div>
            <div style="font-size: 32px; font-weight: bold;">{koniec_cnt}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Zakładki misji (Filtrowanie)
    widok = st.radio("🎯 Wybierz widok roboczy:", ["📋 WSZYSTKIE", "🟢 TYLKO NOWOŚCI", "🟡 TYLKO ZMIANY CEN", "🔴 TYLKO KONIEC PROMOCJI"], horizontal=True)
    
    df_filtered = df.copy()
    if widok == "🟢 TYLKO NOWOŚCI": df_filtered = df_filtered[df_filtered['Status'] == 'NOWOŚĆ']
    elif widok == "🟡 TYLKO ZMIANY CEN": df_filtered = df_filtered[df_filtered['Status'] == 'ZMIANA CENY']
    elif widok == "🔴 TYLKO KONIEC PROMOCJI": df_filtered = df_filtered[df_filtered['Status'] == 'KONIEC PROMOCJI']

    # 3. Przejrzysta Tabela (posortowana działami)
    # Ukrywamy kolumnę EAN w widoku roboczym, żeby odchudzić tabelę (EAN trafi na wydruk)
    edytowany_df = st.data_editor(
        df_filtered,
        hide_index=True,
        use_container_width=True,
        column_config={
            "🖨️ Do druku": st.column_config.CheckboxColumn(required=True),
            "EAN": None, # Ukrywa EAN na pulpicie
            "Departament": st.column_config.TextColumn(width="medium"),
            "Nazwa": st.column_config.TextColumn(width="large")
        }
    )
    
    # --- GENEROWANIE WYDRUKU HTML (Data URI) ---
    do_druku_df = edytowany_df[edytowany_df["🖨️ Do druku"] == True]
    if not do_druku_df.empty:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
            <style>
                @page {{ size: A4 portrait; margin: 10mm; }}
                * {{ box-sizing: border-box; }}
                body {{ font-family: sans-serif; margin: 0; padding: 0; }}
                .container {{ width: 190mm; margin: 0 auto; }}
                .departament-header {{ color: #666; font-size: 14pt; font-weight: bold; margin-top: 20px; border-bottom: 2px solid #eee; text-transform: uppercase; padding-bottom: 4px; }}
                .product-row {{ display: flex; align-items: center; border-bottom: 1px solid #f0f0f0; padding: 12px 0; page-break-inside: avoid; width: 100%; }}
                .col-sku {{ width: 22%; }}
                .sku-text {{ font-size: 11pt; font-weight: bold; margin-bottom: 4px; }}
                .col-nazwa {{ width: 43%; padding: 0 10px; }}
                .status-label {{ font-size: 8pt; color: #0056b3; font-weight: bold; text-transform: uppercase; margin-bottom: 3px; }}
                .nazwa-text {{ font-size: 11pt; font-weight: bold; color: #222; }}
                .col-ceny {{ width: 20%; display: flex; flex-direction: column; align-items: center; }}
                .cena-stara {{ text-decoration: line-through; color: #888; font-size: 9pt; }}
                .cena-nowa {{ font-size: 18pt; font-weight: bold; color: #000; }}
                .mechanizm {{ font-size: 9pt; font-weight: bold; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; border: 1px solid #ccc; }}
                .col-ean {{ width: 15%; text-align: right; font-size: 8pt; color: #999; }}
                svg {{ max-height: 40px; width: 100%; object-fit: contain; }}
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
            barcode_html = f"<svg id='b{sku}'></svg>" if ean.isdigit() and ean != "BRAK_EAN" else "<div style='font-size:7pt;color:#ccc;margin-top:10px;'>Brak EAN</div>"
            if ean.isdigit() and ean != "BRAK_EAN":
                js_barcode_calls += f"JsBarcode('#b{sku}', '{ean}', {{format:'CODE128',width:1.8,height:40,displayValue:false,margin:0}});"
            
            stara_cena = f"Reg: {row['Stara Cena']} zł" if row['Status'] != "NOWOŚĆ" else ""
            mech = f"<div class='mechanizm'>{row['Ilość/Mechanizm']}</div>" if row['Ilość/Mechanizm'] not in ["1", "-", "1 szt."] else ""
            nowa_cena_format = f"{row['Nowa Cena']} zł" if row['Nowa Cena'] != "-" else "-"
            
            html_content += f"""
            <div class='product-row'>
                <div class='col-sku'><div class='sku-text'>{sku}</div>{barcode_html}</div>
                <div class='col-nazwa'><div class='status-label'>{row['Status']}</div><div class='nazwa-text'>{row['Nazwa']}</div></div>
                <div class='col-ceny'><span class='cena-stara'>{stara_cena}</span><span class='cena-nowa'>{nowa_cena_format}</span>{mech}</div>
                <div class='col-ean'>EAN:<br>{ean}</div>
            </div>"""
        
        html_content += f"""
            </div>
            <script>
                window.onload = function() {{ {js_barcode_calls} setTimeout(function() {{ window.print(); }}, 600); }};
            </script>
        </body>
        </html>"""

        b64_html = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
        href = f"data:text/html;base64,{b64_html}"
        
        st.divider()
        st.markdown(f"""
            <a href="{href}" target="_blank" style="text-decoration: none;">
                <div style="padding: 15px; background-color: #0056b3; color: white; text-align: center; border-radius: 8px; font-weight: bold; font-size: 18px; cursor: pointer; border: 1px solid #004494;">
                    🖨️ KLIKNIJ TUTAJ, ABY WYDRUKOWAĆ EKIETY (A4)
                </div>
            </a>
            <p style="text-align: center; color: #666; font-size: 12px; margin-top: 8px;">
                Link bezpiecznie otworzy nową kartę z wygenerowanym szablonem ze zdjęcia.
            </p>
        """, unsafe_allow_html=True)
