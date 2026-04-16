import streamlit as st
import pdfplumber
import csv
import re
import io

# Ustawienia wyglądu strony
st.set_page_config(page_title="Konwerter PDF na CSV", page_icon="📄")

st.title("Asystent Zmiany Cen: PDF ➡️ CSV")
st.write("Wgraj plik PDF z gazetką, a program wyciągnie z niego dane do Excela.")

# Przycisk do wgrywania pliku
uploaded_file = st.file_uploader("Wybierz plik PDF z dysku", type=["pdf"])

if uploaded_file is not None:
    st.info("Trwa analizowanie tabel... To potrwa kilka sekund.")
    
    produkty = []
    
    # Otwieranie wgranego pliku PDF
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 6: continue
                    sku = str(row[1]).strip() if row[1] else ""
                    if not re.match(r'^\d{4,7}$', sku): continue

                    nazwa = str(row[2]).replace('\n', ' ').strip()
                    nazwa = re.sub(r'\s+', ' ', nazwa)
                    cena_reg_str = str(row[3]).replace('\n', '').replace('zł', '').replace(' ', '').strip()
                    mtb = str(row[4]).replace('\n', ' ').strip()
                    ean = str(row[5]).strip()

                    typ = 'S'
                    cena_promo = cena_reg_str
                    ilosc_sztuk = "1"

                    promo_match = re.search(r'(\d+(?:,\d{2})?)\s*zł\s*przy\s*zak\S*\s*(\d+)\s*szt?', mtb, re.IGNORECASE)
                    wychodzi_match = re.search(r'wychodzi\s*(\d+(?:,\d{2})?)\s*zł\s*pomimo\s*(?:\()?(\d+)\+(\d+)', mtb, re.IGNORECASE)

                    if promo_match:
                        typ = 'P'
                        cena_za_szt = float(promo_match.group(1).replace(',', '.'))
                        ilosc = int(promo_match.group(2))
                        cena_promo = str(round(cena_za_szt * ilosc, 2)).replace('.', ',')
                        ilosc_sztuk = str(ilosc)
                    elif wychodzi_match:
                        typ = 'P'
                        ilosc_platnych = int(wychodzi_match.group(2))
                        ilosc_wszystkich = ilosc_platnych + int(wychodzi_match.group(3))
                        cena_reg_float = float(cena_reg_str.replace(',', '.'))
                        cena_promo = str(round(cena_reg_float * ilosc_platnych, 2)).replace('.', ',')
                        ilosc_sztuk = str(ilosc_wszystkich)

                    produkty.append([typ, nazwa, cena_promo, cena_reg_str, ean, ilosc_sztuk, sku])

    st.success(f"✅ SUKCES! Wyodrębniono {len(produkty)} produktów.")

    # Zapisywanie danych do pliku CSV w pamięci (zamiast na dysku)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Typ', 'Nazwa', 'Cena Promo', 'Cena Regularna', 'EAN', 'Ilosc', 'SKU'])
    writer.writerows(produkty)
    
    csv_data = output.getvalue()

    # Przycisk do pobierania gotowego pliku CSV
    st.download_button(
        label="📥 Pobierz plik CSV",
        data=csv_data.encode('utf-8'),
        file_name="dane.csv",
        mime="text/csv",
    )