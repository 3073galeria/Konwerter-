import streamlit as st
import pandas as pd
import re

# Konfiguracja strony
st.set_page_config(page_title="Asystent Dealz", page_icon="🏷️", layout="wide")

# Ukrywamy domyślne elementy Streamlit dla czystszego widoku
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.title("🏷️ Asystent Zmiany Cen Dealz")

# --- SILNIK PARSUJĄCY ---
def parse_text(raw_text):
    full_text = re.sub(r'\s+', ' ', raw_text).strip()
    # Usuwamy nagłówki
    full_text = re.sub(r'Departament SKU SKUDesc.*?ean code', '', full_text, flags=re.IGNORECASE)
    full_text = re.sub(r'GAZETKA P\d+ \d{2}\.\d{2}-\d{2}\.\d{2}', '', full_text, flags=re.IGNORECASE)
    
    # Gilotyna SKU - wyciągamy Dział (np. 820), Nazwę Działu i SKU
    pattern = r'\b(\d{3})\b\s+([A-Z\s&/()]+?)\s+(\d{4,8})\s+(.*?)((?=\b\d{3}\b\s+[A-Z\s&/()]+?\s*\d{4,8}\b)|$)'
    matches = re.finditer(pattern, full_text)
    
    katalog = {}
    
    for match in matches:
        kod_dzialu = match.group(1).strip()
        nazwa_dzialu = match.group(2).strip()
        departament = f"{kod_dzialu} {nazwa_dzialu}"
        sku = match.group(3).strip()
        reszta_tekstu = match.group(4).strip()
        
        # Szukanie pierwszej ceny regularnej (zabezpiecza przed gramaturą)
        reg_price_match = re.search(r'(\d+[.,]\d{2})\s*zł', reszta_tekstu, re.IGNORECASE)
        if not reg_price_match: 
            continue
            
        nazwa = reszta_tekstu[:reg_price_match.start()].strip()
        cena_reg_str = reg_price_match.group(1)
        reszta_po_reg = reszta_tekstu[reg_price_match.end():].strip()
        
        # Wyłapywanie EAN (ignorujemy #ARG!)
        eans = re.findall(r'\*?\b(\d{8,14})\b\*?', reszta_po_reg)
        ean = "BRAK_EAN"
        for e in reversed(eans): # Szukamy od końca, by uniknąć fałszywych trafień
            if e and e != '#ARG!':
                ean = e
                break 
                
        # Sekcja promocyjna (MTB)
        mtb = re.sub(r'\*?\b\d{8,14}\b\*?', '', reszta_po_reg).replace('#ARG!', '').strip()
        
        cena_reg_float = float(cena_reg_str.replace(',', '.'))
        cena_reg_format = "{:.2f}".format(cena_reg_float).replace('.', ',')
        
        typ = 'S'
        cena_promo_format = cena_reg_format
        ilosc_sztuk = '1'
        
        # Logika sprawdzania promocji
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
    stara_text = st.text_area("📄 Wklej tekst STAREJ gazetki:", height=200)
with col2:
    nowa_text = st.text_area("📄 Wklej tekst NOWEJ gazetki:", height=200)

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
                    "Cena Regularna": nowa_dane['Stara_Cena'] + " zł",
                    "Cena Promocyjna": nowa_dane['Nowa_Cena'] + " zł",
                    "Ilość/Mechanizm": nowa_dane['Mechanizm'],
                    "EAN": nowa_dane['EAN']
                })
                
        for sku, stara_dane in stara_baza.items():
            if sku not in nowa_baza:
                wyniki.append({
                    "🖨️ Do druku": False, # Domyślnie końcówki promocji odznaczamy z druku etykiet
                    "Status": "KONIEC PROMOCJI",
                    "Departament": stara_dane['Departament'],
                    "SKU": sku,
                    "Nazwa": stara_dane['Nazwa'],
                    "Cena Regularna": stara_dane['Stara_Cena'] + " zł",
                    "Cena Promocyjna": "-",
                    "Ilość/Mechanizm": "-",
                    "EAN": stara_dane['EAN']
                })

        # Zapisujemy wyniki do sesji
        st.session_state['df_wyniki'] = pd.DataFrame(wyniki)
    else:
        st.warning("Wklej tekst do obu okien!")

# --- INTERAKTYWNA TABELA I WYDRUK ---
if 'df_wyniki' in st.session_state and not st.session_state['df_wyniki'].empty:
    st.divider()
    st.subheader("📋 Lista robocza (Zaznacz, co chcesz wydrukować)")
    st.info("💡 Możesz sortować klikając w nagłówki kolumn. Odznacz pole w kolumnie '🖨️ Do druku', aby pominąć dany produkt na wydruku.")
    
    # Interaktywny edytor danych
    edytowany_df = st.data_editor(
        st.session_state['df_wyniki'],
        hide_index=True,
        use_container_width=True,
        column_config={
            "🖨️ Do druku": st.column_config.CheckboxColumn(required=True)
        }
    )
    
    st.divider()
    
    # --- GENERATOR WYDRUKU (WIDOK DOCELOWY) ---
    st.subheader("🖨️ Podgląd Wydruku")
    
    # Filtrujemy tylko to, co zaznaczone
    do_druku_df = edytowany_df[edytowany_df["🖨️ Do druku"] == True]
    
    if do_druku_df.empty:
        st.warning("Nie wybrano żadnych produktów do druku.")
    else:
        # Sortowanie według departamentów
        do_druku_df = do_druku_df.sort_values(by="Departament")
        
        # Generowanie czystego kodu HTML imitującego gazetkę
        html_head = """
        <html>
        <head>
            <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
            <style>
                body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background: #fff; margin: 0; }
                .departament-header { background: #333; color: #fff; padding: 10px; font-size: 18px; font-weight: bold; margin-top: 20px; text-transform: uppercase; border-radius: 4px; }
                .product-row { display: flex; align-items: center; border-bottom: 1px solid #ddd; padding: 10px 0; page-break-inside: avoid; }
                .col-sku { width: 15%; text-align: center; }
                .col-nazwa { width: 40%; padding: 0 15px; font-size: 14px; font-weight: bold; }
                .col-ceny { width: 25%; text-align: center; }
                .col-ean { width: 20%; text-align: center; font-size: 12px; color: #555; }
                .cena-stara { text-decoration: line-through; color: #888; font-size: 12px; }
                .cena-nowa { color: #d00; font-size: 20px; font-weight: bold; display: block; margin-top: 5px; }
                .mechanizm { background: #ffeb3b; padding: 2px 5px; font-size: 12px; border-radius: 3px; font-weight: bold; }
                svg { max-height: 50px; }
                
                /* Ukryj przycisk drukuj podczas fizycznego wydruku */
                @media print {
                    .btn-print { display: none !important; }
                }
            </style>
        </head>
        <body>
            <button class="btn-print" onclick="window.print()" style="padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-bottom: 10px;">🖨️ Wydrukuj ten arkusz</button>
        """
        
        html_body = ""
        current_dept = ""
        
        # Skrypty JSBarcode będziemy zbierać na koniec
        js_scripts = ""
        
        for index, row in do_druku_df.iterrows():
            dept = row["Departament"]
            if dept != current_dept:
                html_body += f"<div class='departament-header'>{dept}</div>"
                current_dept = dept
            
            ean = str(row["EAN"])
            sku = str(row["SKU"])
            
            # Bezpiecznik EAN (Tylko prawidłowy EAN wygeneruje kod graficzny)
            barcode_svg = ""
            if ean != "BRAK_EAN" and ean.isdigit():
                barcode_id = f"barcode_{sku}"
                barcode_svg = f"<svg id='{barcode_id}'></svg>"
                js_scripts += f"""
                    try {{
                        JsBarcode("#{barcode_id}", "{ean}", {{
                            format: "CODE128", width: 1.5, height: 40, displayValue: false, margin: 0
                        }});
                    }} catch (e) {{ console.log("Błąd kodu: " + "{ean}"); }}
                """
            else:
                barcode_svg = "<div style='color:#ccc; font-size:10px;'>Brak EAN w systemie</div>"

            # Renderowanie rzędu (poziomego)
            mechanizm_html = f"<div class='mechanizm'>{row['Ilość/Mechanizm']}</div>" if row['Ilość/Mechanizm'] not in ["1", "-", "1 szt."] else ""
            
            html_body += f"""
            <div class='product-row'>
                <div class='col-sku'>
                    <div><strong>{sku}</strong></div>
                    <div style='margin-top: 5px;'>{barcode_svg}</div>
                </div>
                <div class='col-nazwa'>
                    <div style='color: #0066cc; font-size: 10px; margin-bottom: 3px;'>{row['Status']}</div>
                    {row['Nazwa']}
                </div>
                <div class='col-ceny'>
                    <span class='cena-stara'>Reg: {row['Cena Regularna']}</span>
                    <span class='cena-nowa'>{row['Cena Promocyjna']}</span>
                    {mechanizm_html}
                </div>
                <div class='col-ean'>
                    EAN: {ean}
                </div>
            </div>
            """
            
        html_footer = f"""
            <script>
                window.onload = function() {{
                    {js_scripts}
                }};
            </script>
        </body>
        </html>
        """
        
        final_html = html_head + html_body + html_footer
        
        # Wyświetlamy gotowy widok HTML
        st.components.v1.html(final_html, height=800, scrolling=True)
