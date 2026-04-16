import streamlit as st
import pdfplumber
import csv
import re
import io

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Konwerter PDF: X/Y Engine", page_icon="⚙️", layout="wide")
st.title("Asystent Zmiany Cen: Silnik X/Y")
st.write("Wgraj plik PDF. Program czyta po fizycznych współrzędnych słów (odporny na łamanie tekstu i brak kolumn).")

# --- FUNKCJE POMOCNICZE (NASZ SILNIK X/Y) ---

def is_sku(word):
    # SKU: 4 do 8 cyfr, fizycznie leży po lewej stronie kartki (x0 < 200 pikseli)
    return bool(re.fullmatch(r"\d{4,8}", word["text"])) and word["x0"] < 200

def is_ean(word):
    # EAN: 7 do 14 cyfr (odporny na gwiazdki), fizycznie po prawej stronie (x0 > 350 pikseli)
    czysty_tekst = re.sub(r'\*', '', word["text"])
    return bool(re.fullmatch(r"\d{7,14}", czysty_tekst)) and word["x0"] > 350

def group_rows(words, tolerance=4):
    # Grupowanie słów w wiersze po osi Y (tolerancja 4 piksele)
    words = sorted(words, key=lambda w: w['top'])
    rows = []
    current_row = []
    current_y = None
    
    for w in words:
        if current_y is None:
            current_y = w['top']
            
        if abs(w['top'] - current_y) <= tolerance:
            current_row.append(w)
        else:
            # Sortujemy zebrany wiersz od lewej do prawej (po osi X)
            rows.append(sorted(current_row, key=lambda x: x['x0']))
            current_row = [w]
            current_y = w['top']
            
    if current_row:
        rows.append(sorted(current_row, key=lambda x: x['x0']))
    return rows

def parse_product(block_words):
    # Sortujemy słowa dla naturalnego czytania (z góry na dół, z lewej do prawej)
    sorted_words = sorted(block_words, key=lambda w: (w['top'], w['x0']))
    full_text = " ".join([w['text'] for w in sorted_words])
    
    sku = "BRAK_SKU"
    ean = "BRAK_EAN"
    
    # Wyciąganie SKU i EAN
    for w in sorted_words:
        if sku == "BRAK_SKU" and is_sku(w):
            sku = w['text']
        if is_ean(w):
            ean = re.sub(r'\*', '', w['text'])
            
    # Wyciąganie wszystkich potencjalnych cen (kropka lub przecinek)
    # Szukamy liczby formatu X,XX lub X.XX
    all_prices = re.findall(r'(\d+[.,]\d{2})', full_text)
    
    cena_reg_str = "0,00"
    cena_promo_str = "0,00"
    typ = 'S'
    ilosc_sztuk = "1"
    
    if all_prices:
        cena_reg_str = all_prices[0].replace('.', ',')
        cena_promo_str = cena_reg_str # Domyślnie brak promocji
        
    # Czyszczenie nazwy (usuwamy SKU, EAN i kody działów np. "820")
    name = full_text
    name = name.replace(sku, '', 1)
    if ean != "BRAK_EAN":
        name = name.replace(ean, '', 1)
    name = re.sub(r'\b\d{3}\b', ' ', name) 
    name = re.sub(r'GAZETKA|Cena sprzedaży|ean code', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\s+', ' ', name).strip()
    
    # --- LOGIKA PROMOCYJNA (Odporna na szum i słowo GRATIS) ---
    # 1. Tor: "2.33 zł przy zak. 2 szt"
    promo_match = re.search(r'(\d+[.,]\d{2})\s*(?:zł|pln)?\s*przy\s*zak\S*\s*(\d+)\s*szt?', full_text, re.IGNORECASE)
    # 2. Tor: "wychodzi 2.33 zł pomimo (2+1 GRATIS)" -> Magnes na X+Y
    wychodzi_match = re.search(r'(\d+)\s*\+\s*(\d+)', full_text)
    
    if promo_match:
        typ = 'P'
        cena_za_szt = float(promo_match.group(1).replace(',', '.'))
        ilosc = int(promo_match.group(2))
        cena_promo_str = str(round(cena_za_szt * ilosc, 2)).replace('.', ',')
        ilosc_sztuk = str(ilosc)
        
    elif wychodzi_match:
        typ = 'P'
        ilosc_platnych = int(wychodzi_match.group(1))
        gratis = int(wychodzi_match.group(2))
        ilosc_wszystkich = ilosc_platnych + gratis
        cena_reg_float = float(cena_reg_str.replace(',', '.'))
        # Skrypt sam liczy łączną cenę wielopaka na podstawie starej ceny
        cena_promo_str = str(round(cena_reg_float * ilosc_platnych, 2)).replace('.', ',')
        ilosc_sztuk = str(ilosc_wszystkich)

    return {
        "Typ": typ, "Nazwa": name, "Cena Promo": cena_promo_str,
        "Cena Regularna": cena_reg_str, "EAN": ean, "Ilosc": ilosc_sztuk, "SKU": sku
    }

# --- GŁÓWNY INTERFEJS ---

uploaded_file = st.file_uploader("Wybierz plik PDF z dysku", type=["pdf"])

if uploaded_file is not None:
    st.info("Odpalam silnik X/Y. Skanuję fizyczne położenie słów...")
    
    all_words = []
    
    # 1. Pobieranie wszystkich słów i ich współrzędnych
    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            all_words.extend(page.extract_words())
            
    # 2. Grupowanie w wiersze
    rows = group_rows(all_words)
    
    # 3. Budowanie bloków (Zasada Gilotyny SKU)
    products_blocks = []
    current_block = []
    
    for row in rows:
        has_sku = any(is_sku(w) for w in row)
        has_ean = any(is_ean(w) for w in row)
        
        # Cięcie Gilotyną - jeśli mamy już jakiś tekst, a wjeżdża nowe SKU -> zamykamy stary blok!
        if has_sku and current_block:
            products_blocks.append(current_block)
            current_block = []
            
        # Zbieramy dane do bloku, jeśli został otwarty
        if has_sku or current_block:
            current_block.extend(row)
            
        # Naturalne zamknięcie bloku (znaleziono EAN na końcu)
        if has_ean and current_block:
            products_blocks.append(current_block)
            current_block = []
            
    # Dodanie ostatniego bloku z pamięci
    if current_block:
        products_blocks.append(current_block)
        
    # 4. Przetwarzanie i Walidacja
    valid_products = []
    
    for block in products_blocks:
        if not block: continue
        parsed = parse_product(block)
        
        # Krytyczna walidacja - dodajemy do CSV tylko jeśli jest poprawny SKU i jakakolwiek Cena
        if parsed["SKU"] != "BRAK_SKU" and parsed["Cena Regularna"] != "0,00":
            # Przygotowanie wiersza pod Twój schemat Excela
            valid_products.append([
                parsed["Typ"], parsed["Nazwa"], parsed["Cena Promo"], 
                parsed["Cena Regularna"], parsed["EAN"], parsed["Ilosc"], parsed["SKU"]
            ])

    # 5. Generowanie pliku
    if valid_products:
        st.success(f"✅ SUKCES! Bezbłędnie wyodrębniono {len(valid_products)} produktów.")
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['Typ', 'Nazwa', 'Cena Promo', 'Cena Regularna', 'EAN', 'Ilosc Sztuk', 'SKU'])
        writer.writerows(valid_products)
        
        csv_data = output.getvalue()
        
        st.download_button(
            label="📥 Pobierz plik CSV dla Excela",
            data=csv_data.encode('utf-8-sig'), 
            file_name="sklep_ceny_XY.csv",
            mime="text/csv",
        )
    else:
        st.error("❌ Nie znalazłem żadnych produktów spełniających kryteria. Upewnij się, że wgrywasz właściwy plik.")
