import streamlit as st
import re

st.set_page_config(page_title="Porównywarka Gazetek Dealz", page_icon="🕵️", layout="wide")
st.title("Asystent Zmiany Cen: Porównywarka i Generator Etykiet 🖨️")
st.write("Wklej tekst ze Starej i Nowej gazetki. Program sam znajdzie zmiany i wygeneruje kody kreskowe!")

# --- FUNKCJA PARSUJĄCA (NASZ SILNIK) ---
def parse_text(raw_text):
    full_text = re.sub(r'\s+', ' ', raw_text).strip()
    full_text = re.sub(r'Departament SKU SKUDesc.*?ean code', '', full_text, flags=re.IGNORECASE)
    full_text = re.sub(r'GAZETKA P\d+ \d{2}\.\d{2}-\d{2}\.\d{2}', '', full_text, flags=re.IGNORECASE)
    
    pattern = r'\b\d{3}\b\s+[A-Z\s&/()]*?\s*(\d{4,8})\s+(.*?)((?=\b\d{3}\b\s+[A-Z\s&/()]*?\s*\d{4,8}\b)|$)'
    matches = re.finditer(pattern, full_text)
    
    katalog = {}
    
    for match in matches:
        sku = match.group(1)
        reszta_tekstu = match.group(2).strip()
        
        reg_price_match = re.search(r'(\d+[.,]\d{2})\s*zł', reszta_tekstu, re.IGNORECASE)
        if not reg_price_match: continue
            
        nazwa = reszta_tekstu[:reg_price_match.start()].strip()
        cena_reg_str = reg_price_match.group(1)
        reszta_po_reg = reszta_tekstu[reg_price_match.end():].strip()
        
        eans = re.findall(r'\*?\b(\d{8,14})\b\*?', reszta_po_reg)
        ean = "BRAK_EAN"
        for e in eans:
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
            ilosc_sztuk = str(ilosc)
        elif x_y_match:
            typ = 'P'
            ilosc_platnych = int(x_y_match.group(1))
            gratis = int(x_y_match.group(2))
            ilosc_sztuk = str(ilosc_platnych + gratis)
            cena_promo_format = "{:.2f}".format(cena_reg_float * ilosc_platnych).replace('.', ',')
        elif simple_price:
            val = float(simple_price.group(1).replace(',', '.'))
            typ = 'P'
            cena_promo_format = "{:.2f}".format(val).replace('.', ',')
            ilosc_sztuk = 'Wielosztuka'
                
        katalog[sku] = {
            'Nazwa': nazwa, 'Cena_Reg': cena_reg_format, 
            'Cena_Promo': cena_promo_format, 'EAN': ean, 
            'Typ': typ, 'Ilosc': ilosc_sztuk
        }
    return katalog

# --- INTERFEJS UŻYTKOWNIKA ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("📄 STARA Gazetka")
    stara_text = st.text_area("Wklej tekst ze starej gazetki:", height=250, key="stara")

with col2:
    st.subheader("📄 NOWA Gazetka")
    nowa_text = st.text_area("Wklej tekst z nowej gazetki:", height=250, key="nowa")

if st.button("🚀 PORÓWNAJ GAZETKI", use_container_width=True):
    if stara_text and nowa_text:
        stara_baza = parse_text(stara_text)
        nowa_baza = parse_text(nowa_text)
        
        nowosci = []
        zmiany_cen = []
        koniec_promocji = []
        
        # LOGIKA ZDERZENIA
        for sku, nowa_dane in nowa_baza.items():
            if sku not in stara_baza:
                nowosci.append((sku, nowa_dane))
            else:
                stara_dane = stara_baza[sku]
                if (nowa_dane['Cena_Reg'] != stara_dane['Cena_Reg'] or 
                    nowa_dane['Cena_Promo'] != stara_dane['Cena_Promo'] or 
                    nowa_dane['Typ'] != stara_dane['Typ'] or 
                    nowa_dane['Ilosc'] != stara_dane['Ilosc']):
                    zmiany_cen.append((sku, nowa_dane, stara_dane))
                    
        for sku, stara_dane in stara_baza.items():
            if sku not in nowa_baza:
                koniec_promocji.append((sku, stara_dane))
        
        # --- PREZENTACJA WYNIKÓW ---
        st.divider()
        
        # 1. KONIEC PROMOCJI (Lista do zdjęcia ze sklepu)
        if koniec_promocji:
            st.error(f"🔴 KONIEC PROMOCJI ({len(koniec_promocji)} produktów) - Zdejmij z półki!")
            for sku, dane in koniec_promocji:
                st.write(f"**SKU:** {sku} | **Nazwa:** {dane['Nazwa']}")
        
        # 2. NOWOŚCI I ZMIANY CEN (Do druku)
        do_druku = nowosci + [(item[0], item[1]) for item in zmiany_cen]
        
        if do_druku:
            st.success(f"🟢 NOWOŚCI I ZMIANY CEN ({len(do_druku)} produktów) - Gotowe do druku!")
            
            # Generowanie układu HTML dla kodów kreskowych
            html_content = """
            <html>
            <head>
                <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
                <style>
                    body { font-family: Arial, sans-serif; }
                    .etykieta { border: 1px dashed #ccc; padding: 10px; margin: 10px; display: inline-block; width: 300px; text-align: center; vertical-align: top; }
                    .nazwa { font-size: 12px; font-weight: bold; margin-bottom: 5px; height: 30px; overflow: hidden; }
                    .cena { font-size: 18px; color: #d9534f; font-weight: bold; margin-bottom: 5px; }
                    .sku { font-size: 10px; color: #555; }
                </style>
            </head>
            <body>
            """
            
            for sku, dane in do_druku:
                # Pokazujemy ceny w zależności od tego, czy to wielosztuka czy standard
                cena_text = f"{dane['Cena_Promo']} zł"
                if dane['Typ'] == 'P' and dane['Ilosc'] != '1':
                    cena_text += f" ({dane['Ilosc']} szt)"
                
                ean_do_kodu = dane['EAN']
                # Bezpiecznik jeśli EAN jest uszkodzony - drukujemy SKU jako zapasowy kod kreskowy
                kod_kreskowy = ean_do_kodu if ean_do_kodu != "BRAK_EAN" else sku 
                
                html_content += f"""
                <div class="etykieta">
                    <div class="nazwa">{dane['Nazwa']}</div>
                    <div class="cena">{cena_text}</div>
                    <svg id="barcode_{sku}"></svg>
                    <div class="sku">SKU: {sku} | EAN: {ean_do_kodu}</div>
                    <script>
                        JsBarcode("#barcode_{sku}", "{kod_kreskowy}", {{
                            format: "CODE128",
                            lineColor: "#000",
                            width: 2,
                            height: 40,
                            displayValue: false
                        }});
                    </script>
                </div>
                """
            
            html_content += "</body></html>"
            
            # Osadzenie gotowego widoku z kodami w aplikacji
            st.components.v1.html(html_content, height=600, scrolling=True)
            
            # Wskazówka dla użytkownika
            st.info("💡 Aby wydrukować powyższe kody, kliknij prawym przyciskiem myszy wewnątrz białego pola z kodami i wybierz 'Drukuj' (lub użyj skrótu Ctrl+P).")
        
        if not nowosci and not zmiany_cen and not koniec_promocji:
            st.success("✅ Brak jakichkolwiek zmian! Obie gazetki są identyczne.")
            
    else:
        st.warning("⚠️ Wklej tekst do obu okien, aby rozpocząć porównanie.")
