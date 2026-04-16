import streamlit as st
import pdfplumber
import csv
import re
import io

# Ustawienia wyglądu strony
st.set_page_config(page_title="Konwerter Gazetek", page_icon="📄")

st.title("Asystent Zmiany Cen: PDF ➡️ CSV")
st.write("Wgraj plik PDF z gazetką. Skrypt używa niezawodnego silnika analizy tekstu i zachowuje polskie znaki w Excelu.")

uploaded_file = st.file_uploader("Wybierz plik PDF z dysku", type=["pdf"])

if uploaded_file is not None:
    st.info("Trwa analizowanie danych... To potrwa kilka sekund.")
    
    text = ""
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            # Używamy extract_text() zamiast tables, bo omija to problem przesuwających się kolumn
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
                
    # --- SILNIK CZYSZCZĄCY I WYODRĘBNIAJĄCY ---
    lines = text.split('\n')
    flat_text = ""
    
    for line in lines:
        line = line.strip()
        # Ignoruj śmieci i nagłówki
        if re.search(r'GAZETKA|Departament|SKU|SKUDesc|Cena sprzedaży|ean code|--- PAGE', line, re.IGNORECASE) or re.match(r'^\[(source|Image).*\]', line, re.IGNORECASE) or line == "":
            continue
        # Ignoruj numery i nazwy działów (żeby nie psuły kodów SKU)
        if re.match(r'^\d{3}$', line) or re.match(r'^(CONFECTIONERY|GROCERY|AMBIENT|PET|SOFT DRINKS|SNACKING|HEALTH & BEAUTY|HEALTH|BEAUTY|EVERYDAY HOME|SEASONAL|HOUSEHOLD|PEPCO|HARD GOODS|BEER/ WINES & SPRITS)$', line, re.IGNORECASE) or re.match(r'^\d{3}\s+(CONFECTIONERY|GROCERY|AMBIENT|PET|SOFT DRINKS|SNACKING|HEALTH & BEAUTY|HEALTH|BEAUTY|EVERYDAY HOME|SEASONAL|HOUSEHOLD|PEPCO|HARD GOODS|BEER/ WINES & SPRITS)', line, re.IGNORECASE) or re.match(r'^\(PEPCO\)$', line, re.IGNORECASE):
            continue
        flat_text += " " + line
        
    flat_text = re.sub(r'\s+', ' ', flat_text).strip()
    
    # Szukamy kotwic, czyli wszystkich cen XX,XX zł
    price_regex = re.compile(r'(\d+[.,]\d{2}\s*(?:zł|pln))', re.IGNORECASE)
    all_prices = list(price_regex.finditer(flat_text))
    
    produkty = []
    
    if all_prices:
        grouped = []
        i = 0
        while i < len(all_prices):
            curr = all_prices[i]
            if i + 1 < len(all_prices):
                nxt = all_prices[i+1]
                text_between = flat_text[curr.end():nxt.start()].strip()
                if text_between == "" or text_between.lower() in ["zł", "pln", "/"]:
                    grouped.append({'old': curr, 'new': nxt})
                    i += 2
                    continue
            grouped.append({'old': curr, 'new': None})
            i += 1
            
        boundaries = [0]
        for i in range(len(grouped) - 1):
            p1 = grouped[i]
            p2 = grouped[i+1]
            end_of_p1 = p1['new'].end() if p1['new'] else p1['old'].end()
            start_of_p2 = p2['old'].start()
            middle_text = flat_text[end_of_p1:start_of_p2]
            
            split_offset = 0
            next_sku_match = re.search(r'\b\d{5,8}\b', middle_text)
            if next_sku_match:
                split_offset = next_sku_match.start()
            else:
                word_match = re.search(r'\s+([A-ZŻŹĆĄŚĘŁÓŃ]{4,})', middle_text)
                if word_match:
                    split_offset = word_match.start() + 1
                else:
                    bracket_match = re.search(r'\)\s+', middle_text)
                    if bracket_match:
                        split_offset = bracket_match.start() + 1
            boundaries.append(end_of_p1 + split_offset)
            
        boundaries.append(len(flat_text))
        
        for i in range(len(grouped)):
            chunk_start = boundaries[i]
            chunk_end = boundaries[i+1]
            chunk = flat_text[chunk_start:chunk_end]
            
            old_price_idx = grouped[i]['old'].start() - chunk_start
            name_block = chunk[:old_price_idx]
            
            if grouped[i]['new']:
                new_price_end = grouped[i]['new'].end() - chunk_start
                promo_block = chunk[new_price_end:].strip()
                final_offer = grouped[i]['new'].group().strip() + " " + promo_block
            else:
                old_price_end = old_price_idx + len(grouped[i]['old'].group())
                promo_block = chunk[old_price_end:].strip()
                final_offer = promo_block if promo_block else grouped[i]['old'].group().strip()
                
            name_block = name_block.strip()
            
            # WYZNACZANIE EAN-u ORAZ JEGO USUNIĘCIE Z NAZWY/OFERTY
            ean_match = re.findall(r'(?:\b\d{13}\b|\*\d{13}\*)', name_block + " " + final_offer)
            ean = ean_match[-1].replace('*', '') if ean_match else "BRAK_EAN"
            
            name_block = re.sub(r'(?:\b\d{13}\b|\*\d{13}\*)', ' ', name_block)
            final_offer = re.sub(r'(?:\b\d{13}\b|\*\d{13}\*)', ' ', final_offer)
            
            # WYZNACZANIE KODU SKU Z NAZWY
            sku_match = re.search(r'\b\d{5,8}\b', name_block)
            if sku_match:
                sku = sku_match.group()
                name_block = name_block.replace(sku, '').strip()
            else:
                sku = "BRAK_SKU"
                
            final_name = re.sub(r'\s+', ' ', name_block).strip()
            final_offer = re.sub(r'\(?MTB\)?', '', final_offer, flags=re.IGNORECASE).strip()
            old_offer = grouped[i]['old'].group().strip()
            
            # --- TWOJA GENIALNA MATEMATYKA (Nienaruszona) ---
            typ = 'S'
            cena_promo = old_offer
            ilosc_sztuk = "1"
            
            promo_match = re.search(r'(\d+(?:,\d{2})?)\s*zł\s*przy\s*zak\S*\s*(\d+)\s*szt?', final_offer, re.IGNORECASE)
            wychodzi_match = re.search(r'wychodzi\s*(\d+(?:,\d{2})?)\s*zł\s*pomimo\s*(?:\()?(\d+)\+(\d+)', final_offer, re.IGNORECASE)
            
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
                cena_reg_float = float(old_offer.replace('zł','').replace(' ','').replace(',', '.'))
                cena_promo = str(round(cena_reg_float * ilosc_platnych, 2)).replace('.', ',')
                ilosc_sztuk = str(ilosc_wszystkich)
            else:
                # Jeśli jest czysta nowa cena np. "7,50 zł" bez zasad sztukowych
                cena_prosta = re.match(r'^(\d+[.,]\d{2})\s*zł$', final_offer, re.IGNORECASE)
                if cena_prosta:
                    cena_promo = cena_prosta.group(1)

            # Dopisywanie do listy wyników
            produkty.append([typ, final_name, cena_promo, old_offer, ean, ilosc_sztuk, sku, final_offer])

    if produkty:
        st.success(f"✅ SUKCES! Wyodrębniono {len(produkty)} produktów.")

        # Zapis do CSV w pamięci (z odpowiednim kodowaniem dla Microsoft Excel)
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Typ', 'Nazwa', 'Cena Promo (wyliczona)', 'Cena Regularna', 'EAN', 'Ilosc Sztuk (wyliczona)', 'SKU', 'Oryginalny Opis Promocji (dla weryfikacji)'])
        writer.writerows(produkty)
        
        csv_data = output.getvalue()

        st.download_button(
            label="📥 Pobierz plik CSV dla Excela",
            # MAGIA EXCELA: 'utf-8-sig' to kodowanie z BOM, które wymusza na Excelu poprawne czytanie polskich znaków Ą, Ę, Ł, Ś
            data=csv_data.encode('utf-8-sig'), 
            file_name="sklep_ceny.csv",
            mime="text/csv",
        )
    else:
        st.error("Nie znalazłem żadnych produktów. Upewnij się, że wgrywasz poprawny plik PDF.")
