import streamlit as st
import pandas as pd
import re
import json

# Konfiguracja strony
st.set_page_config(page_title="Asystent Dealz", page_icon="🏷️", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.title("🏷️ Asystent Zmiany Cen Dealz")

# --- SILNIK PARSUJĄCY (NIETKNIĘTY) ---
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
        if not reg_price_match: 
            continue
            
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
        
        typ = 'S'
        cena_promo_format = cena_reg_format
        ilosc_sztuk = '1'
        
        promo_match = re.search(r'(\d+(?:[.,]\d{1,2})?)\s*(?:zł|pln)?\s*(?:/\s*szt\.?)?\s*przy\s*zak\S*\s*(\d+)', mtb, re.IGNORECASE)
        x_y_match = re.search(r'(\d+)\s*\+\s*(\d+)', mtb)
        simple_price = re.search(r'(\d+(?:[.,]\d{1,2})?)\s*zł', mtb, re.IGNORECASE)
        
        if promo_match:
            typ = 'P'
            cena_za_szt = float(promo_match.group(1).replace(',', '.'))
            ilosc = int(promo_match.group(2))
            cena_promo_format = "{:.2f}".format(cena_za_szt * ilosc).replace('.', ',')
            ilosc_sztuk = f"{ilosc} szt."
        elif x_y_match:
            typ = 'P'
            ilosc_platnych = int(x_y_match.group(1))
            gratis = int(x_y_match.group(2))
            ilosc_sztuk = f"{ilosc_platnych + gratis} szt."
            cena_promo_format = "{:.2f}".format(cena_reg_float * ilosc_platnych).replace('.', ',')
        elif simple_price:
            val = float(simple_price.group(1).replace(',', '.'))
            typ = 'P'
            cena_promo_format = "{:.2f}".format(val).replace('.', ',')
            ilosc_sztuk = 'Wielosztuka'
                
        katalog[sku] = {
            'Departament': departament,
            'Nazwa': nazwa, 
            'Stara_Cena': cena_reg_format, 
            'Nowa_Cena': cena_promo_format, 
            'Mechanizm': ilosc_sztuk,
            'EAN': ean, 
            'Typ': typ
        }
    return katalog

# --- INTERFEJS APLIKACJI ---
col1, col2 = st.columns(2)
with col1:
    stara_text = st.text_area("📄 Wklej tekst STAREJ gazetki:", height=150)
with col2:
    nowa_text = st.text_area("📄 Wklej tekst NOWEJ gazetki:", height=150)

if st.button("🚀 PRZETWÓRZ I PORÓWNAJ", use_container_width=True):
    if stara_text and nowa_text:
        stara_baza = parse_text(stara_text)
        nowa_baza = parse_text(nowa_text)
        
        wyniki = []
        
        for sku, nowa_dane in nowa_baza.items():
            if sku not in stara_baza:
                status = "NOWOŚĆ"
            else:
                stara_dane = stara_baza[sku]
                if (nowa_dane['Stara_Cena'] != stara_dane['Stara_Cena'] or 
                    nowa_dane['Nowa_Cena'] != stara_dane['Nowa_Cena'] or 
                    nowa_dane['Typ'] != stara_dane['Typ'] or 
                    nowa_dane['Mechanizm'] != stara_dane['Mechanizm']):
                    status = "ZMIANA CENY"
                else:
                    status = "BEZ ZMIAN"
            
            if status != "BEZ ZMIAN":
                wyniki.append({
                    "🖨️ Do druku": True,
                    "Status": status,
                    "Departament": nowa_dane['Departament'],
                    "SKU": sku,
                    "Nazwa": nowa_dane['Nazwa'],
                    "Cena Regularna": nowa_dane['Stara_Cena'],
                    "Cena Promocyjna": nowa_dane['Nowa_Cena'],
                    "Ilość/Mechanizm": nowa_dane['Mechanizm'],
                    "EAN": nowa_dane['EAN']
                })
                
        for sku, stara_dane in stara_baza.items():
            if sku not in nowa_baza:
                wyniki.append({
                    "🖨️ Do druku": True, 
                    "Status": "KONIEC PROMOCJI",
                    "Departament": stara_dane['Departament'],
                    "SKU": sku,
                    "Nazwa": stara_dane['Nazwa'],
                    "Cena Regularna": stara_dane['Stara_Cena'],
                    "Cena Promocyjna": "-",
                    "Ilość/Mechanizm": "-",
                    "EAN": stara_dane['EAN']
                })

        st.session_state['df_wyniki'] = pd.DataFrame(wyniki)
    else:
        st.warning("Wklej tekst do obu okien!")

# --- FILTROWANIE I GENEROWANIE WYDRUKU ---
if 'df_wyniki' in st.session_state and not st.session_state['df_wyniki'].empty:
    st.divider()
    
    st.subheader("🎯 Panel misji: Co chcesz dzisiaj wydrukować?")
    
    df = st.session_state['df_wyniki']
    dostepne_statusy = df['Status'].unique().tolist()
    
    wybrane_statusy = st.multiselect(
        "Pokaż tylko produkty o statusie:",
        options=dostepne_statusy,
        default=dostepne_statusy
    )
    
    df_filtered = df[df['Status'].isin(wybrane_statusy)].reset_index(drop=True)
    
    st.markdown("##### 📋 Lista robocza (Zaznacz/Odznacz wybrane)")
    edytowany_df = st.data_editor(
        df_filtered,
        hide_index=True,
        use_container_width=True,
        column_config={
            "🖨️ Do druku": st.column_config.CheckboxColumn(required=True)
        }
    )
    
    # --- PRZYGOTOWANIE KODU HTML DO OKNA DRUKOWANIA ---
    do_druku_df = edytowany_df[edytowany_df["🖨️ Do druku"] == True]
    
    if not do_druku_df.empty:
        do_druku_df = do_druku_df.sort_values(by="Departament")
        
        # HTML z rygorystycznymi blokadami szerokości (A4 Strict CSS)
        html_head = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
            <style>
                @page { size: A4 portrait; margin: 10mm; }
                * { box-sizing: border-box; }
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #fff; margin: 0; padding: 0; color: #000; }
                .container { width: 100%; max-width: 190mm; margin: 0 auto; } /* 210mm A4 minus marginesy */
                
                .departament-header { color: #666; font-size: 16px; font-weight: bold; margin-top: 25px; padding-bottom: 5px; border-bottom: 2px solid #eee; text-transform: uppercase; }
                .product-row { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #f0f0f0; padding: 12px 0; page-break-inside: avoid; width: 100%; overflow: hidden; }
                
                .col-sku { width: 22%; text-align: left; padding-right: 10px; }
                .sku-text { font-size: 14px; font-weight: bold; margin-bottom: 5px; }
                
                .col-nazwa { width: 43%; padding: 0 10px; word-wrap: break-word; }
                .status-label { font-size: 11px; color: #0056b3; font-weight: bold; margin-bottom: 4px; text-transform: uppercase; }
                .nazwa-text { font-size: 14px; font-weight: 600; line-height: 1.2; }
                
                .col-ceny { width: 20%; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; }
                .cena-stara { text-decoration: line-through; color: #888; font-size: 11px; margin-bottom: 2px; }
                .cena-nowa { font-size: 24px; font-weight: bold; color: #000; margin-bottom: 2px; }
                .mechanizm { font-size: 11px; font-weight: bold; color: #444; background: #f9f9f9; padding: 2px 6px; border-radius: 4px; border: 1px solid #e0e0e0; }
                
                .col-ean { width: 15%; text-align: right; font-size: 11px; color: #999; word-wrap: break-word; }
                
                svg { max-height: 45px; width: 100%; object-fit: contain; }
                
                @media print {
                    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
                }
            </style>
        </head>
        <body>
            <div class="container">
        """
        
        html_body = ""
        current_dept = ""
        js_scripts = ""
        
        for index, row in do_druku_df.iterrows():
            dept = row["Departament"]
            if dept != current_dept:
                html_body += f"<div class='departament-header'>{dept}</div>"
                current_dept = dept
            
            ean = str(row["EAN"])
            sku = str(row["SKU"])
            
            barcode_svg = ""
            if ean != "BRAK_EAN" and ean.isdigit():
                barcode_id = f"barcode_{sku}"
                barcode_svg = f"<svg id='{barcode_id}'></svg>"
                js_scripts += f"""
                    try {{
                        JsBarcode("#{barcode_id}", "{ean}", {{
                            format: "CODE128", width: 1.8, height: 40, displayValue: false, margin: 0
                        }});
                    }} catch (e) {{ console.log("Błąd kodu: " + "{ean}"); }}
                """
            else:
                barcode_svg = "<div style='color:#ccc; font-size:10px; margin-top:10px;'>Brak EAN w systemie</div>"

            mechanizm_html = ""
            if row['Ilość/Mechanizm'] not in ["1", "-", "1 szt."]:
                mechanizm_html = f"<div class='mechanizm'>{row['Ilość/Mechanizm']}</div>"
                
            stara_cena_html = f"Reg: {row['Cena Regularna']} zł" if row['Status'] != "NOWOŚĆ" else ""
            nowa_cena_format = f"{row['Cena Promocyjna']} zł" if row['Cena Promocyjna'] != "-" else "-"
            
            html_body += f"""
            <div class='product-row'>
                <div class='col-sku'>
                    <div class='sku-text'>{sku}</div>
                    {barcode_svg}
                </div>
                <div class='col-nazwa'>
                    <div class='status-label'>{row['Status']}</div>
                    <div class='nazwa-text'>{row['Nazwa']}</div>
                </div>
                <div class='col-ceny'>
                    <span class='cena-stara'>{stara_cena_html}</span>
                    <span class='cena-nowa'>{nowa_cena_format}</span>
                    {mechanizm_html}
                </div>
                <div class='col-ean'>
                    EAN:<br>{ean}
                </div>
            </div>
            """
            
        html_footer = f"""
            </div> <script>
                window.onload = function() {{
                    {js_scripts}
                    // Po wygenerowaniu kodów kreskowych automatycznie otwórz okno drukowania
                    setTimeout(function() {{ window.print(); }}, 600);
                }};
            </script>
        </body>
        </html>
        """
        
        final_html = html_head + html_body + html_footer
        
        st.divider()
        st.info("Poniższy przycisk otworzy nową kartę i automatycznie uruchomi systemowe okno drukowania.")
        
        # Konwertujemy HTML do JSON-a, żeby bezpiecznie wstrzyknąć go do JavaScriptu
        html_json = json.dumps(final_html)
        
        # Streamlit Component z przyciskiem wstrzykującym HTML do nowej karty
        st.components.v1.html(f"""
            <button onclick="openPrintWindow()" style="padding: 12px 20px; background: #0066cc; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold; font-family: sans-serif; transition: background 0.3s;">
                🖨️ OTWÓRZ OKNO DRUKOWANIA
            </button>
            <script>
            function openPrintWindow() {{
                var printWindow = window.open('', '_blank');
                printWindow.document.open();
                printWindow.document.write({html_json});
                printWindow.document.close();
            }}
            </script>
        """, height=60)
    else:
        st.info("Zaznacz przynajmniej jeden produkt, aby przygotować wydruk.")
