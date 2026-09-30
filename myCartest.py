# Den Opgraderede Python-kode (Version 2.0)
# Denne version indeholder:
#    1. Udvidet genkendelse af både Bilbasen.dk og DBA.dk (inklusive håndtering af skjulte links).
#    2. Direkte links i SMS'en: Du får nu tilsendt de præcise, klikbare internetadresser på de nye biler direkte på mobilen.
#    3. Professionel logning: Almindelige print()-statements er udskiftet med Pythons officielle logging-modul. Den skriver både til din skærm og gemmer alt i en fil kaldet robot_aktivitet.log. [1, 2, 4, 5, 6] 
import time
import os
import logging
import requests
from playwright.sync_api import sync_playwright

# ==========================================
#         1. KONFIGURATION & LOGNING
# ==========================================
GATEWAYAPI_TOKEN = "HER_INDSÆTTER_DU_DIN_GATEWAYAPI_TOKEN"
MIT_MOBILNUMMER = 4512345678  # Husk 45, intet + eller 00

LINKS_FIL = "soegelinks.txt"
GEMTE_BILER_FIL = "set_biler.txt"
LOG_FIL = "robot_aktivitet.log"

# Opsætning af professionel logning (Skriver til både skærm og logfil)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FIL, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# ==========================================
#            2. FUNKTIONER (LOGIK)
# ==========================================

def load_search_urls():
    """Læser søgelinks og håndterer kommentarer samt tomme linjer"""
    if not os.path.exists(LINKS_FIL):
        with open(LINKS_FIL, "w", encoding="utf-8") as f:
            f.write("# Indsæt dine mobile.de, autoscout24.de, bilbasen.dk eller dba.dk links her:\n")
        return []
    
    urls = []
    with open(LINKS_FIL, "r", encoding="utf-8") as f:
        for line in f.readlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls

def load_seen_cars():
    """Henter listen over bil-links, vi allerede har sendt SMS om"""
    if os.path.exists(GEMTE_BILER_FIL):
        with open(GEMTE_BILER_FIL, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_seen_cars(seen_cars_set):
    """Gemmer listen over sete biler permanent"""
    with open(GEMTE_BILER_FIL, "w", encoding="utf-8") as f:
        for car_link in seen_cars_set:
            f.write(f"{car_link}\n")

def send_sms_via_gatewayapi(message):
    """Sender SMS med de direkte links til din telefon via GatewayAPI"""
    url = "https://gatewayapi.com"
    payload = {
        "sender": "BilRobot",          
        "message": message,            
        "recipients": [{"msisdn": MIT_MOBILNUMMER}]
    }
    try:
        response = requests.post(url, json=payload, auth=(GATEWAYAPI_TOKEN, ""), timeout=10)
        if response.status_code == 200:
            logging.info("✅ SMS afsendt succesfuldt via GatewayAPI!")
        else:
            logging.error(f"❌ GatewayAPI fejl. Status: {response.status_code}, Svar: {response.text}")
    except Exception as e:
        logging.error(f"🚨 Kunne ikke forbinde til GatewayAPI: {e}")

def scrape_site_with_browser(url):
    """Åbner browseren og trækker direkte links ud fra Mobile, AutoScout, Bilbasen eller DBA"""
    found_car_links = []
    
    # Identificer platform ud fra URL-teksten
    if "mobile.de" in url:
        site_name = "Mobile.de"
    elif "autoscout24" in url:
        site_name = "AutoScout24"
    elif "bilbasen.dk" in url:
        site_name = "Bilbasen"
    elif "dba.dk" in url:
        site_name = "DBA.dk"
    else:
        site_name = "Ukendt side"

    with sync_playwright() as p:
        # headless=True betyder at browseren kører usynligt i baggrunden
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        try:
            logging.info(f"🌐 Åbner {site_name}...")
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # --- PLATFORM 1: MOBILE.DE ---
            if site_name == "Mobile.de":
                elements = page.query_selector_all("article")
                for el in elements:
                    car_id = el.get_attribute("data-ad-id")
                    if car_id:
                        found_car_links.append(f"https://mobile.de{car_id}")
            
            # --- PLATFORM 2: AUTOSCOUT24 ---
            elif site_name == "AutoScout24":
                elements = page.query_selector_all("[data-guid]")
                for el in elements:
                    car_id = el.get_attribute("data-guid")
                    if car_id:
                        found_car_links.append(f"https://autoscout24.de{car_id}")
            
            # --- PLATFORM 3: BILBASEN.DK ---
            elif site_name == "Bilbasen":
                # Vent på bil-kortene indlæses på skærmen
                page.wait_for_selector("[data-testid='listing']", timeout=5000)
                elements = page.query_selector_all("[data-testid='listing']")
                for el in elements:
                    # Bilbasen gemmer typisk linket i et almindeligt 'a'-tag indeni kortet
                    link_element = el.query_selector("a")
                    if link_element:
                        href = link_element.get_attribute("href")
                        if href and "/brugt/bil/" in href:
                            # Sørg for det bliver til et fuldt link
                            fuld_url = href if href.startswith("http") else f"https://www.bilbasen.dk{href}"
                            found_car_links.append(fuld_url)
            
            # --- PLATFORM 4: DBA.DK ---
            elif site_name == "DBA.dk":
                page.wait_for_selector(".dbaCard", timeout=5000)
                elements = page.query_selector_all(".dbaCard")
                for el in elements:
                    link_element = el.query_selector("a")
                    if link_element:
                        href = link_element.get_attribute("href")
                        if href:
                            fuld_url = href if href.startswith("http") else f"https://www.dba.dk{href}"
                            found_car_links.append(fuld_url)
                            
        except Exception as e:
            logging.error(f"❌ Fejl under skrabning af {site_name}: {e}")
        finally:
            browser.close()
            
    return found_car_links

# ==========================================
#               3. HOVEDLOOP
# ==========================================
if __name__ == "__main__":
    logging.info("🚀 Bil-Robot startet succesfuldt! Overvågning er aktiv.")
    logging.info("Husk at teste med 'time.sleep(10)' i bunden før fuld drift.\n")

    while True:
        try:
            soegelinks = load_search_urls()
            seen_cars = load_seen_cars()
            
            if not soegelinks:
                logging.warning("⚠️ 'soegelinks.txt' er tom! Indsæt links for at scanne.")
            else:
                all_found_links = []
                
                # Kør igennem alle links i din tekstfil
                for index, url in enumerate(soegelinks, 1):
                    logging.info(f"Scanning i gang: Link {index} af {len(soegelinks)}")
                    links_fra_side = scrape_site_with_browser(url)
                    all_found_links.extend(links_fra_side)
                
                logging.info(f"📊 Scanning færdig. Fandt i alt {len(all_found_links)} biler på tværs af platforme.")
                
                # Filtrer så vi KUN har helt nye biler, vi aldrig har set før
                new_cars = [link for link in all_found_links if link not in seen_cars]
                
                if new_cars:
                    logging.info(f"✨ HURRA! Fandt {len(new_cars)} NYE bilbiler på markedet.")
                    
                    # Tilføj de nye links til vores historik-fil
                    for link in new_cars:
                        seen_cars.add(link)
                    save_seen_cars(seen_cars)
                    
                    # Byg SMS-beskeden med de direkte links
                    sms_tekst = f"BilRobot Match! Fandt {len(new_cars)} ny(e) bil(er):\n"
                    for link in new_cars:
                        sms_tekst += f"- {link}\n"
                    
                    # Hvis beskeden bliver for lang til én SMS, korter vi den ned
                    if len(sms_tekst) > 800:
                        sms_tekst = sms_tekst[:750] + "\n...og flere links! Tjek dine søgninger."
                        
                    send_sms_via_gatewayapi(sms_tekst)
                else:
                    logging.info("💤 Ingen nye annoncer fundet siden sidste tjek.")
                    
        except Exception as global_err:
            logging.critical(f"🚨 KRITISK SYSTEMFEJL I HOVEDLOOP: {global_err}")
            
        # 🛡️ DETERMINISTISK TIMER (Tids-loop)
        # Sæt til 10 sekunder under test. Sæt til 1800 (30 minutter) i produktion.
        logging.info("⏳ Går i dvale. Venter på næste scanning...\n")
        time.sleep(1800)