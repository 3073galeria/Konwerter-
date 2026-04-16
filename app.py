import streamlit as st
import pdfplumber
import csv
import re
import io

st.set_page_config(page_title="Konwerter Gazetek", page_icon="📄", layout="wide")
st.title("Asystent Zmiany Cen: Smart Cells 🧠")
st.write("Silnik odporny na przesunięcia kolumn, brakujące kody i wymysły działu marketingu.")

uploaded_file = st.file_uploader("Wybierz plik PDF z dysku (np. P26 - P29)", type=["pdf"])

if uploaded_file is not None:
    st.info("Skanuję tabelę przy użyciu Inteligentnych Komórek (Smart Cells)...")
    
    produkty = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row: continue
                    
                    # Czyścimy komórki z pustych znaków i enterów
                    cells = [str(c).replace('\n', ' ').strip() for c in row if c and str(c).strip()]
                    if len(cells) < 3: continue # Ignorujemy śmieciowe, za krótkie wiersze
                    
                    sku = ""
                    ean = "BRAK_EAN"
                    cena_reg_str = ""
                    promo_text = ""
                    nazwa_parts = []
                    
                    # Analizujemy KAŻDĄ komórkę w wierszu niezależnie od jej pozycji
                    for cell in cells:
                        c_low = cell.lower()
                        
                        # 1. Ignorowanie nagłówków i śmieci
                        if any(x in c_low for x in ['gazetka', 'cena sprzedaży', 'ean code', 'typ', 'confectionery']):
                            continue
                            
                        # 2. Szukanie EAN (8-14 cyfr, może mieć gwiazdki)
                        if re.fullmatch(r'\*?\d{8,14}\*?', cell.replace(' ', '')):
                            ean = cell.replace('*', '').replace(' ', '')
                            continue
                            
                        # 3. Szukanie SKU (4-8 cyfr, zazwyczaj pierwszy znaleziony numer)
                        if not sku and re.fullmatch(r'\d{4,8}', cell):
                            sku = cell
                            continue
                            
                        # 4. Szukanie Opisu Promocji (słowa klucze)
                        if re.search(r'(przy\s*zak|wychodzi|\+)', cell, re.IGNORECASE) or re.search(r'\d+\s*szt', cell, re.IGNORECASE):
                            promo_text = cell
                            continue
                            
                        # 5. Szukanie Ceny Regularnej (Samotne XX,XX zł)
                        if not cena_reg_str and re.fullmatch(r'\d+[.,]\d{2}\s*(?:zł|pln)?', cell, re.IGNORECASE):
                            cena_reg_str = cell.replace(' zł', '').replace('zł', '').replace(' ', '')
                            continue
                            
                        # 6. Ignorowanie samotnych kodów działów (np. "820")
                        if re.fullmatch(r'\d{3}', cell):
                            continue
                            
                        # 7. Reszta to Nazwa Produktu
                        nazwa_parts.append(cell)
                        
                    # Jeśli nie znaleziono SKU, to znaczy, że to nie jest produkt (tylko np. stopka strony)
                    if not sku:
                        continue
                        
                    # Sklejamy nazwę do kupy i usuwamy podwójne spacje
                    nazwa = " ".join(nazwa_parts).strip()
                    nazwa = re.sub(r'\s+', ' ', nazwa)
                    
                    # --- MATEMATYKA I FORMATOWANIE ---
                    
                    # Gwarantujemy, że cena będzie miała format XX,XX (dla Excela)
                    if cena_reg_str:
                        try:
                            cena_reg_float = float(cena_reg_str.replace(',', '.'))
                            cena_reg_format = "{:.2f}".format(cena_reg_float).replace('.', ',')
                        except ValueError:
                            cena_reg_float = 0.0
                            cena_reg_format = "0,00"
                    else:
                        cena_reg_float = 0.0
                        cena_reg_format = "0,00"
                        
                    typ = 'S'
                    cena_promo_format = cena_reg_format
                    ilosc_sztuk = '1'
                    
                    # Przeliczanie promocji
                    if promo_text:
                        promo_match = re.search(r'(\d+[.,]\d{2})\s*(?:zł|pln)?\s*przy\s*zak\S*\s*(\d+)\s*szt?', promo_text, re.IGNORECASE)
                        wychodzi_match = re.search(r'wychodzi\s*(\d+[.,]\d{2})\s*zł\s*pomimo\s*(?:\()?\s*(\d+)\s*\+\s*(\d+)', promo_text, re.IGNORECASE)
                        
                        if promo_match:
                            typ = 'P'
                            cena_za_szt = float(promo_match.group(1).replace(',', '.'))
                            ilosc = int(promo_match.group(2))
                            cena_promo_format = "{:.2f}".format(cena_za_szt * ilosc).replace('.', ',')
                            ilosc_sztuk = str(ilosc)
                        elif wychodzi_match:
                            typ = 'P'
                            ilosc_platnych = int(wychodzi_match.group(2))
                            gratis = int(wychodzi_match.group(3))
                            ilosc_wszystkich = ilosc_platnych + gratis
                            cena_promo_format = "{:.2f}".format(cena_reg_float * ilosc_platnych).replace('.', ',')
                            ilosc_sztuk = str(ilosc_wszystkich)
                            
                    # ŻELAZNA OCHRONA EXCELA PRZED UCIĘCIEM EAN
                    ean_excel = f'="{ean}"' if ean != "BRAK_EAN" else "BRAK_EAN"
                    
                    produkty.append([typ, nazwa, cena_promo_format, cena_reg_format, ean_excel, ilosc_sztuk, sku])

    if produkty:
        st.success(f"✅ SUKCES! Znalazłem i posprzątałem {len(produkty)} produktów.")
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Typ', 'Nazwa', 'Cena Promo', 'Cena Regularna', 'EAN', 'Ilosc Sztuk', 'SKU'])
        writer.writerows(produkty)
        
        csv_data = output.getvalue()
        
        st.download_button(
            label="📥 Pobierz plik CSV dla Excela",
            data=csv_data.encode('utf-8-sig'), 
            file_name="sklep_ceny_smart_cells.csv",
            mime="text/csv",
        )
    else:
        st.error("❌ Nie znalazłem produktów. Upewnij się, że wgrywasz właściwy plik PDF.")
