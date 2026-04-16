import streamlit as st
import pdfplumber
import csv
import re
import io

st.set_page_config(page_title="Konwerter Gazetek", page_icon="📄", layout="wide")
st.title("Asystent Zmiany Cen: PDF ➡️ CSV")
st.write("Silnik oparty na klasycznym czytaniu tabel z ulepszoną matematyką i ochroną dla Excela.")

uploaded_file = st.file_uploader("Wybierz plik PDF z dysku", type=["pdf"])

if uploaded_file is not None:
    st.info("Trwa analizowanie tabel...")
    
    produkty = []
    
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Omijamy puste i za krótkie wiersze
                    if not row or len(row) < 6:
                        continue
                        
                    sku = str(row[1]).strip() if row[1] else ''
                    
                    # Weryfikacja SKU (4-8 cyfr)
                    if not re.match(r'^\d{4,8}$', sku):
                        continue
                        
                    nazwa = str(row[2]).replace('\n', ' ').strip()
                    nazwa = re.sub(r'\s+', ' ', nazwa)
                    
                    cena_reg_str = str(row[3]).replace('\n', '').replace('zł', '').replace(' ', '').replace(',', '.').strip()
                    mtb = str(row[4]).replace('\n', ' ').strip()
                    ean = str(row[5]).strip()
                    
                    # --- OCHRONA EXCELA ---
                    # Formatujemy EAN jako formułę tekstową, żeby Excel nie ucinał zer ani nie robił E+11
                    ean_excel = f'="{ean}"' if ean else '="BRAK_EAN"'
                    
                    typ = 'S'
                    
                    # --- FORMATOWANIE CEN NA SZTYWNO (XX,XX) ---
                    try:
                        cena_reg_float = float(cena_reg_str)
                        # Wymusza np. 10.00 zamiast 10, a potem zmienia na polski przecinek
                        cena_reg_format = "{:.2f}".format(cena_reg_float).replace('.', ',')
                    except ValueError:
                        cena_reg_float = 0.0
                        cena_reg_format = cena_reg_str
                        
                    cena_promo_format = cena_reg_format
                    ilosc_sztuk = '1'
                    
                    # --- NASZE ULEPSZONE REGEXY ---
                    # Łapie ceny z kropką i przecinkiem
                    promo_match = re.search(r'(\d+[.,]\d{2})\s*(?:zł|pln)?\s*przy\s*zak\S*\s*(\d+)\s*szt?', mtb, re.IGNORECASE)
                    
                    # Ignoruje wszystko co jest za cyframi X+Y (np. "GRATIS")
                    wychodzi_match = re.search(r'wychodzi\s*(\d+[.,]\d{2})\s*zł\s*pomimo\s*(?:\()?\s*(\d+)\s*\+\s*(\d+)', mtb, re.IGNORECASE)
                    
                    if promo_match:
                        typ = 'P'
                        cena_za_szt = float(promo_match.group(1).replace(',', '.'))
                        ilosc = int(promo_match.group(2))
                        cena_promo_format = "{:.2f}".format(cena_za_szt * ilosc).replace('.', ',')
                        ilosc_sztuk = str(ilosc)
                        
                    elif wychodzi_match:
                        typ = 'P'
                        ilosc_platnych = int(wychodzi_match.group(2))
                        ilosc_wszystkich = ilosc_platnych + int(wychodzi_match.group(3))
                        cena_promo_format = "{:.2f}".format(cena_reg_float * ilosc_platnych).replace('.', ',')
                        ilosc_sztuk = str(ilosc_wszystkich)
                        
                    produkty.append([typ, nazwa, cena_promo_format, cena_reg_format, ean_excel, ilosc_sztuk, sku])

    if produkty:
        st.success(f"✅ SUKCES! Wyodrębniono {len(produkty)} produktów.")
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Typ', 'Nazwa', 'Cena Promo', 'Cena Regularna', 'EAN', 'Ilosc Sztuk', 'SKU'])
        writer.writerows(produkty)
        
        csv_data = output.getvalue()
        
        st.download_button(
            label="📥 Pobierz plik CSV dla Excela",
            data=csv_data.encode('utf-8-sig'), 
            file_name="sklep_ceny_poprawione.csv",
            mime="text/csv",
        )
    else:
        st.error("❌ Nie znalazłem produktów. Upewnij się, że wgrywasz właściwy plik PDF.")
