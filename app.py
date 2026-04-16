import streamlit as st
import csv
import re
import io

st.set_page_config(page_title="Konwerter Tekstu z Gazetki", page_icon="✂️", layout="wide")
st.title("Asystent Zmiany Cen: Wklejacz Tekstu ✂️")
st.write("Skopiuj tekst z PDF-a (Ctrl+A, Ctrl+C) i wklej go poniżej.")

raw_text = st.text_area("Wklej tekst ze skopiowanej tabeli PDF tutaj:", height=300)

if st.button("Analizuj tekst i generuj CSV"):
    if raw_text.strip():
        st.info("Przetwarzam surowy tekst...")
        
        # 1. Czyszczenie tekstu z niepotrzebnych spacji i nagłówków
        full_text = re.sub(r'\s+', ' ', raw_text).strip()
        full_text = re.sub(r'Departament SKU SKUDesc.*?ean code', '', full_text, flags=re.IGNORECASE)
        full_text = re.sub(r'GAZETKA P\d+ \d{2}\.\d{2}-\d{2}\.\d{2}', '', full_text, flags=re.IGNORECASE)
        
        # 2. Pocięcie na bloki (Zasada: Kod działu [3 cyfry] -> Nazwa działu -> SKU -> Reszta)
        pattern = r'\b\d{3}\b\s+[A-Z\s&/()]*?\s*(\d{4,8})\s+(.*?)((?=\b\d{3}\b\s+[A-Z\s&/()]*?\s*\d{4,8}\b)|$)'
        matches = re.finditer(pattern, full_text)
        
        produkty = []
        
        for match in matches:
            sku = match.group(1)
            reszta_tekstu = match.group(2).strip()
            
            # 3. Szukanie PIERWSZEJ Ceny Regularnej (zawsze z dopiskiem 'zł')
            reg_price_match = re.search(r'(\d+[.,]\d{2})\s*zł', reszta_tekstu, re.IGNORECASE)
            
            if not reg_price_match:
                continue
                
            nazwa = reszta_tekstu[:reg_price_match.start()].strip()
            cena_reg_str = reg_price_match.group(1)
            
            # Tekst po cenie regularnej (zawiera promocję i EAN)
            reszta_po_reg = reszta_tekstu[reg_price_match.end():].strip()
            
            # 4. Wyciąganie EAN
            # Centrala dubluje EAN-y w nowym pliku, wyłapujemy pierwszy sensowny i ignorujemy #ARG!
            eans = re.findall(r'\*?\b(\d{8,14})\b\*?|#ARG!', reszta_po_reg)
            ean = "BRAK_EAN"
            for e in eans:
                if e and e != '#ARG!':
                    ean = e
                    break 
                    
            # 5. Czyszczenie Opisu Promocji (MTB) ze wszystkich EAN-ów i gwiazdek
            mtb = re.sub(r'\*?\b\d{8,14}\b\*?', '', reszta_po_reg).replace('#ARG!', '').strip()
            
            # --- MATEMATYKA ---
            cena_reg_float = float(cena_reg_str.replace(',', '.'))
            cena_reg_format = "{:.2f}".format(cena_reg_float).replace('.', ',')
            
            typ = 'S'
            cena_promo_format = cena_reg_format
            ilosc_sztuk = '1'
            
            # Reguły na promocje
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
                ilosc_wszystkich = ilosc_platnych + gratis
                cena_promo_format = "{:.2f}".format(cena_reg_float * ilosc_platnych).replace('.', ',')
                ilosc_sztuk = str(ilosc_wszystkich)
                
            elif simple_price:
                # Jeśli program znajdzie samą cenę po prawej (np. zwykła obniżka 25,00 zł -> 20,00 zł)
                val = float(simple_price.group(1).replace(',', '.'))
                if val < cena_reg_float:
                    typ = 'P'
                    cena_promo_format = "{:.2f}".format(val).replace('.', ',')
                    
            # Tarcza dla Excela
            ean_excel = f'="{ean}"' if ean != "BRAK_EAN" else "BRAK_EAN"
            
            produkty.append([typ, nazwa, cena_promo_format, cena_reg_format, ean_excel, ilosc_sztuk, sku])

        if produkty:
            st.success(f"✅ BINGO! Rozkodowano i przeliczono {len(produkty)} produktów.")
            
            output = io.StringIO()
            writer = csv.writer(output, delimiter=';')
            writer.writerow(['Typ', 'Nazwa', 'Cena Promo', 'Cena Regularna', 'EAN', 'Ilosc Sztuk', 'SKU'])
            writer.writerows(produkty)
            
            csv_data = output.getvalue()
            
            st.download_button(
                label="📥 Pobierz plik CSV dla Excela",
                data=csv_data.encode('utf-8-sig'), 
                file_name="sklep_ceny_wklejacz.csv",
                mime="text/csv",
            )
        else:
            st.error("❌ Program nie wyłapał żadnych produktów. Upewnij się, że wkleiłeś tekst bezpośrednio z gazetki.")
else:
    st.warning("⚠️ Pole tekstowe jest puste. Wklej tekst przed kliknięciem!")
