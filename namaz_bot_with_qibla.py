import asyncio
import logging
import aiohttp
import math
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, \
    Contact, ChatJoinRequest, Location
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
import re
from functools import lru_cache
from typing import Optional, Dict, List

# ============ ASOSIY KONFIGURATSIYA ============
API_TOKEN = "8464001114:AAFFtFduO09aEGlaJWdxLEVsksjx0ZzfPc8"
CHANNEL_ID = "-1003691528165"

# ============ LOGGING ============
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============ BOT ============
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ============ GLOBAL DATA ============
user_region = {}
user_district = {}
user_location = {}
user_confirmed = set()

# ============ CACHE ============
prayer_times_cache = {}  # {city: {date: times}}
video_cache = {}  # {category: {videos, timestamp}}
CACHE_DURATION = 3600  # 1 soat

# ============ QIBLA KOORDINATALARI ============
KAABA_LAT = 21.4225  # Makka, Ka'ba
KAABA_LON = 39.8262

# ============ VILOYATLAR VA TUMANLAR ============
REGIONS_WITH_DISTRICTS = {
    "Toshkent shahri": {
        "city": "Tashkent",
        "districts": ["Bektemir", "Chilonzor", "Mirzo Ulug'bek", "Mirobod", "Sergeli", "Shayxontohur", "Yashnobod",
                      "Yunusabad"]
    },
    "Toshkent viloyati": {
        "city": "Tashkent",
        "districts": ["Angren", "Bekabad", "Ohangaron", "Angren t.", "Buka", "Chinobod", "Oqqo'rgon", "Axskent",
                      "Qibray", "Quyichirchiq", "Yangiyul", "Yuqorichirchiq", "Zangiota"]
    },
    "Andijon viloyati": {
        "city": "Andijan",
        "districts": ["Andijon", "Asaka", "Baliqchi", "Buloqboshi", "Jalaquduq", "Izboskan", "Marhamat", "Oltinko'l",
                      "Pakhtaobod", "Qo'rg'ontepa", "Shahrixon", "Xojaobod"]
    },
    "Farg'ona viloyati": {
        "city": "Fergana",
        "districts": ["Beshariq", "Bog'dod", "Buvayda", "Dang'ara", "Farg'ona", "Furqat", "Kuva", "Margilan", "Rishton",
                      "Quva", "Tashloq", "Uzun", "Yozyovon"]
    },
    "Namangan viloyati": {
        "city": "Namangan",
        "districts": ["Chust", "Mingbulok", "Asgon", "Chust t.", "Kosonsoy", "Mingbulok t.", "Mingkul", "Namangan t.",
                      "Norin", "Pachkamar", "Turalkhan", "Uchkurgan", "Uychi", "Yangikurgan"]
    },
    "Samarqand viloyati": {
        "city": "Samarkand",
        "districts": ["Bulung'ur", "Gijduvon", "Jambay", "Kattakurgan", "Katta Ariq", "Kitob", "Oqdaryo", "Payariq",
                      "Pastdarg'om", "Qo'shrabot", "Samarqand t.", "Takhtakaracha", "Tuyoq", "Urgut"]
    },
    "Buxoro viloyati": {
        "city": "Bukhara",
        "districts": ["Alatau", "Buxoro", "Gijduvan", "Goshaun", "Jondor", "Karakul", "Karmana", "Kogon", "Olot",
                      "Peshkun", "Romitan", "Samanqishloq", "Shofirkon", "Vabkent"]
    },
    "Navoiy viloyati": {
        "city": "Navoi",
        "districts": ["Akdaryo", "Gazli", "Karmana", "Konimex", "Kungrad", "Navoiy", "Nurota", "Tomdi", "Uchquduq"]
    },
    "Qashqadaryo viloyati": {
        "city": "Qarshi",
        "districts": ["Guzar", "Kamashi", "Kitob", "Koson", "Mirbozor", "Nishon", "Qamashi", "Qarshi", "Shahrisabz",
                      "Tenniuz", "Yakkabag"]
    },
    "Surxondaryo viloyati": {
        "city": "Termez",
        "districts": ["Angor", "Bandihon", "Boysun", "Denov", "Jarqo'rg'on", "Jomboy", "Kumqo'rg'on", "Muzrabot",
                      "Oltinsoy", "Sariosiyo", "Shodmahn", "Surkhon", "Shurobod", "Termiz", "Uzun", "Halolkuh"]
    },
    "Jizzax viloyati": {
        "city": "Jizzakh",
        "districts": ["Arpali", "Do'stlik", "Forish", "G'allaorol", "Jizzax", "Mirzachol", "Paxtakor", "Sharafkhona",
                      "Yangi Namangan", "Zaamin", "Zarbedaryo"]
    },
    "Sirdaryo viloyati": {
        "city": "Gulistan",
        "districts": ["Boyalinch", "Gulistan", "Mirzaobod", "Oqoltin", "Qoqon", "Sirdaryodaryo", "Tumenbaeva",
                      "Xonabad"]
    },
    "Xorazm viloyati": {
        "city": "Urgench",
        "districts": ["Bog'ot", "Xazarasp", "Xiva", "Khomeli", "Orol", "Shumanay", "Urgench", "Xojayli"]
    },
    "Qoraqalpog'iston Respublikasi": {
        "city": "Nukus",
        "districts": ["Amudaryo", "Aral", "Ashufa", "Beruniy", "Bustan", "Chimboy", "Elliq Qala", "Gazli", "Jandarya",
                      "Jiymbay", "Kegeyli", "Moynak", "Nukus", "Qonlidaryo", "Qo'ng'irot", "Shumanay", "Takhtakopir",
                      "Takhiatosh", "Tangbay", "To'rtko'l", "Tura", "Tuyamuyun", "Xojayli"]
    }
}

# ============ MASHHUR MASJIDLAR ============
MOSQUES = {
    "Tashkent": [
        {"name": "Bibi-Xonum Masjidi", "lat": 41.2956, "lng": 69.1881, "address": "Amir Temur Shox ko'chasi, Toshkent"},
        {"name": "Kiya Masjidi", "lat": 41.3031, "lng": 69.1755, "address": "Oqsa ko'chasi, Toshkent"},
        {"name": "Minor Masjidi", "lat": 41.2874, "lng": 69.1878, "address": "Mirzo Ulug'bek ko'chasi, Toshkent"},
        {"name": "Barak Khan Masjidi", "lat": 41.2944, "lng": 69.1842, "address": "Madrasasi ko'chasi, Toshkent"},
        {"name": "Tillo Shayx Masjidi", "lat": 41.3000, "lng": 69.1800, "address": "Chilonzor Shox ko'chasi, Toshkent"},
        {"name": "Shayx Mohammad Zarifiy Masjidi", "lat": 41.2850, "lng": 69.2050,
         "address": "Bektemir ko'chasi, Toshkent"},
        {"name": "Hazrat Ali Masjidi", "lat": 41.3100, "lng": 69.1700, "address": "Yunus Rajabiy ko'chasi, Toshkent"},
        {"name": "Qoraqul Masjidi", "lat": 41.2750, "lng": 69.2200, "address": "Mirzo Ulug'bek ko'chasi, Toshkent"},
    ],
    "Andijan": [
        {"name": "Jome Masjidi", "lat": 40.7519, "lng": 72.6362, "address": "Andijon Shahar Markazi"},
        {"name": "Xabib Nazar Masjidi", "lat": 40.7400, "lng": 72.6300, "address": "Lenin ko'chasi, Andijon"},
        {"name": "Hasrat Imam Masjidi", "lat": 40.7600, "lng": 72.6500, "address": "Shayx Nomiqull ko'chasi, Andijon"},
    ],
    "Fergana": [
        {"name": "Jome Masjidi", "lat": 40.3814, "lng": 71.7664, "address": "Farg'ona Shahar Markazi"},
        {"name": "Hazrat Qobosolmoliq Masjidi", "lat": 40.3900, "lng": 71.7500,
         "address": "Safarqul ko'chasi, Farg'ona"},
        {"name": "Yunus Rajabiy Masjidi", "lat": 40.3700, "lng": 71.7800, "address": "Shahrikhon ko'chasi, Farg'ona"},
    ],
    "Namangan": [
        {"name": "Jome Masjidi", "lat": 40.9941, "lng": 71.6725, "address": "Namangan Shahar Markazi"},
        {"name": "Hazrat Ubaydulloh Khan Masjidi", "lat": 41.0000, "lng": 71.6600,
         "address": "Buyuk Ipak Yo'li ko'chasi, Namangan"},
    ],
    "Samarkand": [
        {"name": "Bibi-Xonum Masjidi", "lat": 39.6545, "lng": 67.4746, "address": "Registan Sahobi, Samarqand"},
        {"name": "Tilo Shayx Masjidi", "lat": 39.6600, "lng": 67.4800, "address": "Samarqand Shahar Markazi"},
        {"name": "Shohizinda Masjidi", "lat": 39.6700, "lng": 67.4900, "address": "Shohizinda Ko'chasi, Samarqand"},
    ],
    "Bukhara": [
        {"name": "Kalayon Masjidi", "lat": 39.7701, "lng": 64.4161, "address": "Buxoro Shahar Markazi"},
        {"name": "Mir-i Arab Madrassa", "lat": 39.7750, "lng": 64.4200, "address": "Tokhi Zargaron ko'chasi, Buxoro"},
    ],
    "Khiva": [
        {"name": "Jome Masjidi", "lat": 41.3781, "lng": 60.3614, "address": "Xiva Shahar Markazi"},
    ],
    "Nukus": [
        {"name": "Jome Masjidi", "lat": 42.4647, "lng": 59.5631, "address": "Nukus Shahar Markazi"},
    ],
}

# ============ QUR'ON DU'OLARI ============
QURAN_DUAS_FULL = {
    1: {"name": "🥣 Saharlik Duosi", "arabic": "وَبَارَكَ اللهُ لَكُمْ فِي صِيَامِكُمْ",
        "transliteration": "Va barakallohu lakum fi siyamikum", "meaning": "Alloh sizning ro'zaingizni muborak qilsin",
        "category": "Ro'za"},
    2: {"name": "🍽 Iftar Duosi", "arabic": "اللّهُمَّ لَكَ صُمْتُ وَعَلَى رِزْقِكَ أَفْطَرْتُ",
        "transliteration": "Allahumma laka sumtu wa 'ala rizqika aftartu",
        "meaning": "Ey Alloh! Men Sen uchun ro'za tutdim va rizqing bilan ochdim", "category": "Ro'za"},
    3: {"name": "🌙 Yotish Duosi", "arabic": "بِسْمِكَ اللَّهُمَّ أَمُوتُ وَأَحْيَا",
        "transliteration": "Bismika allahumma amutu wa ahya",
        "meaning": "Ey Alloh! Senning nomingda o'lim va hayot keladi", "category": "Kundalik"},
    4: {"name": "🌅 Oyg'onish Duosi", "arabic": "الحَمْدُ لِلَّهِ الَّذِي أَحْيَانَا بَعْدَ مَا أَمَاتَنَا",
        "transliteration": "Alhamdulillah allathi ahyana ba'da ma amatana",
        "meaning": "Hamdu lillahi - O'limdan keyin biz tirilganiga rahmat", "category": "Kundalik"},
    5: {"name": "🤲 Mog'firat Duosi", "arabic": "أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ",
        "transliteration": "Astaghfirullaha al-'adhim",
        "meaning": "Allohdan mog'firat so'rayman va unga taubа qilayman", "category": "Taubа"},
    6: {"name": "🙏 Shukr Duosi", "arabic": "الحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ",
        "transliteration": "Alhamdulillah rabbi al-'alamin",
        "meaning": "Hamdu lillahi - dunyoviy va akhirotiy ne'matlariga rahmat", "category": "Shukr"},
    7: {"name": "👨‍👩‍👧 Ota-onaga du'o", "arabic": "رَبِّ اغْفِرْ لَهُمَا كَمَا رَبَّيَانِي صَغِيرًا",
        "transliteration": "Rabbi ighfir lahuma kama rabbayanee sagheera",
        "meaning": "Ey Rabbim! Ota-onaga mog'firat bergin va rahm qilgin", "category": "Oila"},
    8: {"name": "📚 Bilim Duosi", "arabic": "رَبِّ زِدْنِي عِلْمًا وَهَبْ لِي فَهْمًا",
        "transliteration": "Rabbi zidni 'ilman wa hab li fahman",
        "meaning": "Ey Rabbim! Meni bilim bilan orttirib, fahmni ayn qilgin", "category": "O'qish"},
    9: {"name": "💪 Kuch-quvvat Duosi", "arabic": "وَلا حَوْلَ وَلا قُوَّةَ إِلاّ بِاللهِ",
        "transliteration": "Wa la hawla wa la quwwata illa billah", "meaning": "Kuch va quvvat faqat Allohdan",
        "category": "Sabr"},
    10: {"name": "❤️ Hidoya Duosi", "arabic": "رَبَّنَا لا تُزِغْ قُلُوبَنَا بَعْدَ إِذْ هَدَيْتَنَا",
         "transliteration": "Rabbana la tuzigh qulubana ba'da idh hadaitana",
         "meaning": "Ey Rabbim! Seni topgandan keyin bizning yuraklarimizni bertmas qil", "category": "Iman"},
    11: {"name": "🕌 Ibrohim Du'o", "arabic": "رَبَّنَا وَاجْعَلْنَا مُسْلِمَيْنِ لَكَ",
         "transliteration": "Rabbana wa j'alna muslimain laka", "meaning": "Ey Rabbim! Bizni sanga to'liq taslim bo'l",
         "category": "Iman"},
    12: {"name": "🌟 Nuh Du'o", "arabic": "رَبِّ اغْفِرْ لِي وَلِوَالِدَيَّ",
         "transliteration": "Rabbi ighfir li wa li-walidayya", "meaning": "Ey Rabbim! Menga va ota-onaga mog'firat ber",
         "category": "Mog'firat"},
    13: {"name": "💰 Rizq Duosi", "arabic": "رَبَّنَا آتِنَا فِي الدُّنْيَا حَسَنَةً",
         "transliteration": "Rabbana atina fi ad-dunya hasanah",
         "meaning": "Ey Rabbim! Bizga dunyo va akhirotda xayrliqni ber", "category": "Dunya"},
    14: {"name": "😔 Sabr Duosi", "arabic": "اللَّهُمَّ أَصْبِرْ قَلْبِي عَلَى طَاعَتِكَ",
         "transliteration": "Allahumma asbir qalbi 'ala ta'atik",
         "meaning": "Ey Alloh! Mening yuragimni sening ibodat qilishga sabr ber", "category": "Sabr"},
    15: {"name": "👶 Farzandlar du'o", "arabic": "رَبَّنَا هَبْ لَنَا مِنْ أَزْوَاجِنَا وَذُرِّيَّاتِنَا",
         "transliteration": "Rabbana hab lana min azwajina wa dhurriyyatina",
         "meaning": "Ey Rabbim! Bizga xotinlardan va farzandlardan ko'z quvonch ber", "category": "Oila"},
    16: {"name": "🤝 Dostlar du'o", "arabic": "اللَّهُمَّ اغْفِرْ لَهُم وَارْحَمْهُم",
         "transliteration": "Allahumma ighfir lahum wa arhamhum", "meaning": "Ey Alloh! Ularga mog'firat ber, rahm qil",
         "category": "Oila"},
    17: {"name": "🏥 Kasal du'o", "arabic": "بِسْمِ اللَّهِ أَرْقِيكَ مِنْ كُلِّ شَيْءٍ",
         "transliteration": "Bismillahi arqika min kulli shay'in",
         "meaning": "Allohning nomida, sizni shifoga ko'rsatsin", "category": "Shifoli"},
    18: {"name": "🚗 Safar Duosi", "arabic": "سُبْحَانَ الَّذِي سَخَّرَ لَنَا هَذَا",
         "transliteration": "Subhana alladhi sakhkhara lana hadha",
         "meaning": "Pok Alloh - shu vositani bizga tadbir qilgan", "category": "Safar"},
    19: {"name": "🎯 Niyat Duosi", "arabic": "اللَّهُمَّ إِنِّي أُرِيدُ الْحَج فَيَسِّرْهُ",
         "transliteration": "Allahumma inni uridu al-hajja fa yassirhu",
         "meaning": "Ey Alloh! Men hajj qilmoqchi bo'lyapman, uni menga oson qilgin", "category": "Ibadat"},
    20: {"name": "✨ Tawhid Duosi", "arabic": "لا إِلَهَ إِلاّ اللهُ وَحْدَهُ",
         "transliteration": "La ilaha illallahu wahdahu", "meaning": "Allohdan boshqa hech kim Alloh emas",
         "category": "Tawhid"},
    21: {"name": "🌅 Sabohgi Du'o", "arabic": "اللَّهُمَّ بِكَ أَصْبَحْنَا", "transliteration": "Allahumma bika asbahna",
         "meaning": "Ey Alloh! Senning nomingda saboh bo'ldik", "category": "Kundalik"},
    22: {"name": "🌙 Akshomgi Du'o", "arabic": "اللَّهُمَّ إِنِّي أَسْأَلُكَ الْعَفْوَ",
         "transliteration": "Allahumma inni as'aluka al-'afwa",
         "meaning": "Ey Alloh! Men salbqdan 'afu va xo'jalik so'rayman", "category": "Kundalik"},
    23: {"name": "🤲 Istifar Du'o", "arabic": "سُبْحَانَكَ اللَّهُمَّ وَبِحَمْدِكَ",
         "transliteration": "Subhanaka allahumma wa bihamdik", "meaning": "Pok Sensan Alloh va hamdu",
         "category": "Taubа"},
    24: {"name": "👁️ Ko'z Duosi", "arabic": "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ",
         "transliteration": "Allahumma inni a'udhu bika",
         "meaning": "Ey Alloh! Men salbqdan rangili ko'zdan himoya so'rayman", "category": "Himoya"},
    25: {"name": "🙏 Namozdan Keyin Du'o", "arabic": "اللَّهُمَّ أَنْتَ السَّلامُ",
         "transliteration": "Allahumma anta as-salam", "meaning": "Ey Alloh! Sen salomsan va salbqdan salom keladi",
         "category": "Namoz"}
}

# ============ MA'RUZALAR - SAYTDAN OLINADI ============
LECTURE_CATEGORIES = {
    "quran": {
        "name": "📖 Qur'on tilovati",
        "search_url": "https://muslim.uz/uz/quran-app",
        "keywords": ["quran", "qur'on", "tilovat"]
    },
    "islam": {
        "name": "🎓 Islom asoslari",
        "search_url": "https://muslim.uz/uz/articles",
        "keywords": ["islom", "asoslar", "ta'lim"]
    },
    "namaz": {
        "name": "🕌 Namoz o'rgatish",
        "search_url": "https://muslim.uz/uz/namaz",
        "keywords": ["namoz", "namaz", "salat"]
    },
    "hadith": {
        "name": "📚 Hadislar to'plami",
        "search_url": "https://muslim.uz/uz/hadith",
        "keywords": ["hadis", "hadith", "sunna"]
    },
    "dua": {
        "name": "💭 Kundalik zikrlar",
        "search_url": "https://muslim.uz/uz/dua",
        "keywords": ["zikr", "duo", "dua"]
    }
}


# ============ QIBLA HISOBLASH FUNKSIYALARI ============
def calculate_qibla_direction(user_lat: float, user_lon: float) -> Dict:
    """
    Foydalanuvchi joylashuvidan qiblaga yo'nalishni hisoblash
    """
    # Radianlarga o'tkazish
    lat1 = math.radians(user_lat)
    lon1 = math.radians(user_lon)
    lat2 = math.radians(KAABA_LAT)
    lon2 = math.radians(KAABA_LON)
    
    # Qibla yo'nalishini hisoblash
    dlon = lon2 - lon1
    
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    
    bearing = math.atan2(y, x)
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360
    
    # Masofa hisoblash (km)
    R = 6371  # Yer radiusi km da
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c
    
    # Yo'nalish nomini aniqlash
    directions = [
        "Shimol", "Shimoliy-sharq", "Sharq", "Janubiy-sharq",
        "Janub", "Janubiy-g'arb", "G'arb", "Shimoliy-g'arb"
    ]
    direction_index = round(bearing / 45) % 8
    direction_name = directions[direction_index]
    
    return {
        "bearing": round(bearing, 2),
        "direction": direction_name,
        "distance": round(distance, 2)
    }


def get_qibla_compass_text(qibla_data: Dict, user_lat: float, user_lon: float) -> str:
    """
    Qibla kompas ma'lumotlarini formatlash
    """
    bearing = qibla_data['bearing']
    direction = qibla_data['direction']
    distance = qibla_data['distance']
    
    # Vizual kompas
    compass = get_visual_compass(bearing)
    
    text = (
        f"🧭 <b>QIBLA YO'NALISHI</b>\n\n"
        f"{compass}\n\n"
        f"📍 <b>Sizning joylashuvingiz:</b>\n"
        f"   Kenglik: {user_lat:.4f}°\n"
        f"   Uzunlik: {user_lon:.4f}°\n\n"
        f"🕋 <b>Ka'baga yo'nalish:</b>\n"
        f"   Burchak: {bearing}°\n"
        f"   Yo'nalish: {direction}\n"
        f"   Masofa: {distance:,.0f} km\n\n"
        f"📱 <b>Qo'llanma:</b>\n"
        f"1. Telefoningizni tekis tutib turing\n"
        f"2. Kompas strelkasi Ka'bani ko'rsatishi kerak\n"
        f"3. {direction} tomonga yuzlaningsiz ({bearing}°)\n\n"
        f"💡 <i>Aniq yo'nalish uchun telefoningizning kompasini ishlatishingiz mumkin</i>"
    )
    
    return text


def get_visual_compass(bearing: float) -> str:
    """
    Vizual kompas yaratish (ASCII art)
    """
    # 8 yo'nalish uchun belgilar
    markers = ["⬆️", "↗️", "➡️", "↘️", "⬇️", "↙️", "⬅️", "↖️"]
    
    # Qaysi yo'nalishni ko'rsatish kerak
    index = round(bearing / 45) % 8
    
    # Kompas chizish
    compass_lines = [
        "        ⬆️ S",
        "    ↖️     ↗️",
        "  ⬅️ G   Sh ➡️",
        "    ↙️  🕋 ↘️",
        "        ⬇️ J"
    ]
    
    # Qibla yo'nalishini belgilash
    qibla_marker = "🎯"
    
    # Qibla yo'nalishini ko'rsatuvchi strelka
    arrow = markers[index]
    
    compass_display = "\n".join(compass_lines)
    compass_display += f"\n\n      {arrow} Qibla bu tomonda"
    
    return compass_display


# ============ ASINXRON VIDEO QIDIRISH (TEZ) ============
async def search_videos_from_site(category_key: str) -> Optional[Dict]:
    """
    Asinxron ravishda saytdan videolarni qidirish - JUDA TEZ!
    """
    try:
        # Keshdan tekshirish
        current_time = datetime.now().timestamp()
        if category_key in video_cache:
            cache_data = video_cache[category_key]
            if current_time - cache_data['timestamp'] < CACHE_DURATION:
                logger.info(f"✅ Video keshdan olindi: {category_key}")
                return cache_data['data']

        category = LECTURE_CATEGORIES.get(category_key)
        if not category:
            return None

        url = category['search_url']
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        # Asinxron HTTP so'rov - TEZ!
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    return None

                html = await response.text()

        soup = BeautifulSoup(html, 'html.parser')
        videos = []

        # YouTube video linklar
        youtube_links = soup.find_all('iframe', src=re.compile(r'youtube\.com|youtu\.be'))
        for iframe in youtube_links[:5]:
            video_url = iframe.get('src', '')
            if 'youtube.com/embed/' in video_url:
                video_id = video_url.split('embed/')[-1].split('?')[0]
                videos.append({
                    'title': f"Video {len(videos) + 1}",
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'thumbnail': f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                })

        # Video teglar
        video_tags = soup.find_all('video')
        for video in video_tags[:3]:
            source = video.find('source')
            if source:
                videos.append({
                    'title': f"Video {len(videos) + 1}",
                    'url': source.get('src', ''),
                    'thumbnail': video.get('poster', '')
                })

        # A teglardan video linklar
        video_links = soup.find_all('a', href=re.compile(r'youtube\.com|youtu\.be|\.mp4|video'))
        for link in video_links[:5]:
            href = link.get('href', '')
            if 'youtube.com/watch' in href or 'youtu.be/' in href:
                videos.append({
                    'title': link.get_text(strip=True) or f"Video {len(videos) + 1}",
                    'url': href,
                    'thumbnail': ''
                })

        result = {
            'category': category['name'],
            'videos': videos[:8],
            'page_url': url
        }

        # Keshga saqlash
        video_cache[category_key] = {
            'data': result,
            'timestamp': current_time
        }

        logger.info(f"✅ Yangi videolar yuklandi: {category_key} - {len(videos)} ta")
        return result

    except asyncio.TimeoutError:
        logger.error(f"⏱️ Timeout: {category_key}")
        return None
    except Exception as e:
        logger.error(f"❌ Video qidirishda xatolik: {e}")
        return None


# ============ ASINXRON NAMOZ VAQTLARI (TEZ) ============
async def get_prayer_times_async(city: str, date: Optional[datetime] = None) -> Optional[Dict]:
    """
    Asinxron ravishda namoz vaqtlarini olish - JUDA TEZ!
    """
    try:
        # Keshdan tekshirish
        date_key = date.strftime("%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d")
        cache_key = f"{city}_{date_key}"

        if city in prayer_times_cache and date_key in prayer_times_cache[city]:
            logger.info(f"✅ Namoz vaqti keshdan olindi: {city} - {date_key}")
            return prayer_times_cache[city][date_key]

        # API URL
        if date:
            date_str = date.strftime("%d-%m-%Y")
            url = f"https://api.aladhan.com/v1/timingsByCity/{date_str}?city={city}&country=Uzbekistan&method=2"
        else:
            url = f"https://api.aladhan.com/v1/timingsByCity?city={city}&country=Uzbekistan&method=2"

        # Asinxron HTTP so'rov
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                if response.status == 200:
                    data = await response.json()
                    times = data["data"]["timings"]

                    # Keshga saqlash
                    if city not in prayer_times_cache:
                        prayer_times_cache[city] = {}
                    prayer_times_cache[city][date_key] = times

                    logger.info(f"✅ Yangi namoz vaqti yuklandi: {city} - {date_key}")
                    return times

        return None

    except asyncio.TimeoutError:
        logger.error(f"⏱️ Timeout: Namoz vaqti API - {city}")
        return None
    except Exception as e:
        logger.error(f"❌ Namoz vaqti xatolik: {e}")
        return None


# ============ TUGMALAR ============
def get_channel_join_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔓 Yopiq kanalga a'zo bo'ling", url="https://t.me/+Q6npQqsmJHViNWEy")],
        [InlineKeyboardButton(text="✅ Qo'shilish sorovini yubordim", callback_data="already_sent_request")]
    ])


def regions_keyboard():
    buttons = []
    regions_list = list(REGIONS_WITH_DISTRICTS.keys())
    for i in range(0, len(regions_list), 2):
        row = []
        row.append(InlineKeyboardButton(text=f"📍 {regions_list[i]}", callback_data=f"region_{regions_list[i]}"))
        if i + 1 < len(regions_list):
            row.append(
                InlineKeyboardButton(text=f"📍 {regions_list[i + 1]}", callback_data=f"region_{regions_list[i + 1]}"))
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def districts_keyboard(region_name):
    districts = REGIONS_WITH_DISTRICTS[region_name]['districts']
    buttons = []
    for i in range(0, len(districts), 2):
        row = []
        row.append(
            InlineKeyboardButton(text=f"🏘️ {districts[i]}", callback_data=f"district_{region_name}_{districts[i]}"))
        if i + 1 < len(districts):
            row.append(InlineKeyboardButton(text=f"🏘️ {districts[i + 1]}",
                                            callback_data=f"district_{region_name}_{districts[i + 1]}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="🔙 Viloyatlarga qaytish", callback_data="back_to_regions")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def roza_duas_keyboard():
    buttons = []
    for dua_id, dua in QURAN_DUAS_FULL.items():
        if dua['category'] == "Ro'za":
            buttons.append([InlineKeyboardButton(text=dua['name'], callback_data=f"roza_dua_{dua_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def duas_category_keyboard():
    categories = set(d['category'] for d in QURAN_DUAS_FULL.values())
    buttons = [[InlineKeyboardButton(text=f"📖 {cat}", callback_data=f"cat_{cat}")] for cat in sorted(categories)]
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def duas_by_category_keyboard(category):
    buttons = []
    for dua_id, dua in QURAN_DUAS_FULL.items():
        if dua['category'] == category:
            buttons.append([InlineKeyboardButton(text=dua['name'], callback_data=f"dua_{dua_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Kategoriyalarga qaytish", callback_data="duas_categories")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def lectures_keyboard():
    buttons = []
    for key, category in LECTURE_CATEGORIES.items():
        buttons.append([InlineKeyboardButton(text=category['name'], callback_data=f"lecture_cat_{key}")])
    buttons.append([InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def videos_keyboard(videos, category_key):
    buttons = []
    for i, video in enumerate(videos):
        buttons.append([InlineKeyboardButton(
            text=f"▶️ {video['title'][:40]}...",
            callback_data=f"video_{category_key}_{i}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Ma'ruzalar", callback_data="lectures_list")])
    buttons.append([InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_to_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def video_detail_keyboard(video_url, category_key):
    buttons = [
        [InlineKeyboardButton(text="▶️ Videoni ochish", url=video_url)],
        [InlineKeyboardButton(text="🔙 Videolar ro'yxati", callback_data=f"lecture_cat_{category_key}")],
        [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def qibla_keyboard():
    """Qibla kompas tugmalari"""
    buttons = [
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_qibla")],
        [InlineKeyboardButton(text="🗺️ Google Maps'da Ko'rish", callback_data="qibla_maps")],
        [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu():
    buttons = [
        [KeyboardButton(text="🕌 Bugungi namoz vaqtlari"), KeyboardButton(text="🌙 Ro'za vaqtlari")],
        [KeyboardButton(text="📿 QUR'ONDAGI DU'OLAR (25+)"), KeyboardButton(text="📅 7 kunlik jadval")],
        [KeyboardButton(text="🎓 Ma'ruzalar"), KeyboardButton(text="📍 ENG YAQIN MASJIDNI TOPISH")],
        [KeyboardButton(text="🧭 QIBLA KOMPASI"), KeyboardButton(text="🔁 Viloyatni o'zgartirish")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def location_request_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)]],
                               resize_keyboard=True)


# ============ MASOFANI HISOBLASH ============
@lru_cache(maxsize=128)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    distance = R * c
    return distance


def find_nearest_mosque(user_lat, user_lon, city):
    if city not in MOSQUES:
        return None

    mosques = MOSQUES[city]
    nearest_mosque = None
    min_distance = float('inf')

    for mosque in mosques:
        distance = calculate_distance(user_lat, user_lon, mosque['lat'], mosque['lng'])
        if distance < min_distance:
            min_distance = distance
            nearest_mosque = mosque.copy()
            nearest_mosque['distance'] = distance

    return nearest_mosque


def get_google_maps_url(from_lat, from_lon, to_lat, to_lon, mosque_name):
    return f"https://www.google.com/maps/dir/{from_lat},{from_lon}/{to_lat},{to_lon}/?api=1"


def get_qibla_maps_url(user_lat, user_lon):
    """Qibla yo'nalishi uchun Google Maps URL"""
    return f"https://www.google.com/maps/dir/{user_lat},{user_lon}/{KAABA_LAT},{KAABA_LON}/?api=1"


async def check_channel_membership(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ["creator", "administrator", "member"]
    except:
        return False


async def is_user_ready(user_id: int, message: Message) -> bool:
    if not await check_channel_membership(user_id):
        await message.answer("❌ <b>Siz hali kanalga a'zo emassiz!</b>\n\n🔓 Yopiq kanalga a'zo bo'ling!",
                             reply_markup=get_channel_join_keyboard(), parse_mode="HTML")
        return False
    return True


# ============ HANDLERS ============

@dp.chat_join_request()
async def approve_join_request(update: ChatJoinRequest):
    try:
        user_id = update.from_user.id
        await bot.approve_chat_join_request(CHANNEL_ID, user_id)
        user_confirmed.add(user_id)
        await bot.send_message(user_id,
                               "✅ <b>Siz kanalga a'zo bo'ldingiz!</b>\n\n🌍 <b>Viloyatingizni tanlang:</b>",
                               reply_markup=regions_keyboard(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"❌ Xatolik: {e}")


@dp.message(F.content_type == "location")
async def location_received(message: Message):
    try:
        user_id = message.from_user.id

        if not await is_user_ready(user_id, message):
            return

        if user_id not in user_region:
            await message.answer("❌ <b>Avvalo viloyatni tanlang!</b>", reply_markup=regions_keyboard())
            return

        user_location[user_id] = (message.location.latitude, message.location.longitude)

        region_name = user_region[user_id]
        city = REGIONS_WITH_DISTRICTS[region_name]['city']

        nearest_mosque = find_nearest_mosque(message.location.latitude, message.location.longitude, city)

        if not nearest_mosque:
            await message.answer(f"❌ <b>{city}</b> da masjid ma'lumotlari topilmadi.", reply_markup=main_menu())
            return

        google_maps_url = get_google_maps_url(
            message.location.latitude,
            message.location.longitude,
            nearest_mosque['lat'],
            nearest_mosque['lng'],
            nearest_mosque['name']
        )

        mosque_text = (
            f"🕌 <b>ENG YAQIN MASJID TOPILDI!</b>\n\n"
            f"📍 <b>Masjid nomi:</b> {nearest_mosque['name']}\n"
            f"📮 <b>Manzili:</b> {nearest_mosque['address']}\n"
            f"📏 <b>Sizdan masofasi:</b> {nearest_mosque['distance']:.2f} km\n"
            f"🧭 <b>Koordinatalar:</b> {nearest_mosque['lat']}, {nearest_mosque['lng']}\n\n"
            f"🗺️ <b>Google Maps'da ochish:</b>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗺️ Google Maps'da ko'rish", url=google_maps_url)],
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="back_to_main")]
        ])

        await message.answer(mosque_text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"❌ Xatolik: {e}")
        await message.answer(f"❌ Xatolik yuz berdi: {e}")


@dp.message(F.text == "/start")
async def start_handler(message: Message):
    user_id = message.from_user.id
    if not await check_channel_membership(user_id):
        await message.answer("🔓 <b>YOPIQ KANALGA A'ZO BO'LING!</b>", reply_markup=get_channel_join_keyboard(),
                             parse_mode="HTML")
        return
    if user_id not in user_region:
        await message.answer("🌍 <b>Viloyatingizni tanlang:</b>", reply_markup=regions_keyboard(), parse_mode="HTML")
        return
    await message.answer(f"<b>Assalom! {message.from_user.first_name}!</b>\n\n<b>Menyu:</b>", reply_markup=main_menu(),
                         parse_mode="HTML")


@dp.message(F.text == "/help")
async def help_handler(message: Message):
    help_text = (
        "ℹ️ <b>BOT HAQIDA MA'LUMOT</b>\n\n"
        "Bu bot sizga quyidagi xizmatlarni taqdim etadi:\n\n"
        "🕌 <b>Namoz vaqtlari</b> - Bugungi va haftalik namoz vaqtlarini ko'rish\n"
        "🌙 <b>Ro'za vaqtlari</b> - Saharlik va iftar vaqtlari\n"
        "📿 <b>Qur'ondagi du'olar</b> - 25+ ta du'o to'plami\n"
        "📍 <b>Yaqin masjid</b> - Eng yaqin masjidni topish\n"
        "🧭 <b>Qibla kompasi</b> - Qibla yo'nalishini aniqlash\n"
        "📅 <b>Jadval</b> - 7 kunlik namoz vaqtlari jadvali\n"
        "🎓 <b>Ma'ruzalar</b> - Islomiy ma'ruzalar va video darsliklar\n\n"
        "<b>Buyruqlar:</b>\n"
        "/start - Botni ishga tushirish\n"
        "/help - Yordam va ma'lumot\n\n"
        "📞 <b>Aloqa:</b> @YourSupportUsername"
    )
    await message.answer(help_text, parse_mode="HTML")


@dp.message(F.text == "🧭 QIBLA KOMPASI")
async def qibla_compass_handler(message: Message):
    """Qibla kompasi - joylashuv so'rash"""
    user_id = message.from_user.id
    
    if not await is_user_ready(user_id, message):
        return
    
    await message.answer(
        "🧭 <b>QIBLA KOMPASI</b>\n\n"
        "📍 Qibla yo'nalishini aniqlash uchun joylashuvingizni yuboring!\n\n"
        "🗺️ Quyidagi tugmani bosib, joriy joylashuvingizni ulashing:",
        reply_markup=location_request_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "refresh_qibla")
async def refresh_qibla_handler(callback):
    """Qibla ma'lumotlarini yangilash"""
    user_id = callback.from_user.id
    
    if user_id not in user_location:
        await callback.answer("❌ Avval joylashuvni yuboring!", show_alert=True)
        return
    
    user_lat, user_lon = user_location[user_id]
    qibla_data = calculate_qibla_direction(user_lat, user_lon)
    qibla_text = get_qibla_compass_text(qibla_data, user_lat, user_lon)
    
    # Qibla Maps URL
    maps_url = get_qibla_maps_url(user_lat, user_lon)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_qibla")],
        [InlineKeyboardButton(text="🗺️ Google Maps'da Ko'rish", url=maps_url)],
        [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(qibla_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("✅ Yangilandi!", show_alert=False)


@dp.message(F.text == "🎓 Ma'ruzalar")
async def lectures_handler(message: Message):
    user_id = message.from_user.id
    if not await is_user_ready(user_id, message):
        return

    await message.answer(
        "🎓 <b>ISLOMIY MA'RUZALAR VA VIDEOLAR</b>\n\n"
        "📺 Kategoriyani tanlang:",
        reply_markup=lectures_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("lecture_cat_"))
async def lecture_category_handler(callback):
    """YANGI - TEZ ISHLAYDI!"""
    category_key = callback.data.replace("lecture_cat_", "")

    await callback.message.edit_text(
        "⏳ <b>Videolar yuklanmoqda...</b>",
        parse_mode="HTML"
    )

    # Asinxron qidirish - TEZ!
    result = await search_videos_from_site(category_key)

    if not result or not result['videos']:
        await callback.message.edit_text(
            f"❌ <b>{LECTURE_CATEGORIES[category_key]['name']}</b> uchun videolar topilmadi.\n\n"
            f"🔗 <b>Saytga o'ting:</b> {LECTURE_CATEGORIES[category_key]['search_url']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌐 Saytni ochish", url=LECTURE_CATEGORIES[category_key]['search_url'])],
                [InlineKeyboardButton(text="🔙 Ma'ruzalar", callback_data="lectures_list")],
                [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_to_main")]
            ]),
            parse_mode="HTML"
        )
        return

    text = (
        f"📺 <b>{result['category']}</b>\n\n"
        f"🎬 <b>Topilgan videolar:</b> {len(result['videos'])} ta\n\n"
        f"Videoni tanlang:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=videos_keyboard(result['videos'], category_key),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("video_"))
async def video_detail_handler(callback):
    """Video tafsilotlari - keshdan"""
    parts = callback.data.split("_")
    category_key = parts[1]
    video_index = int(parts[2])

    # Keshdan olish
    if category_key in video_cache:
        result = video_cache[category_key]['data']
    else:
        result = await search_videos_from_site(category_key)

    if not result or video_index >= len(result['videos']):
        await callback.answer("❌ Video topilmadi", show_alert=True)
        return

    video = result['videos'][video_index]

    text = (
        f"▶️ <b>{video['title']}</b>\n\n"
        f"📚 <b>Kategoriya:</b> {result['category']}\n\n"
        f"🔗 <b>Video havolasi:</b>\n{video['url']}\n\n"
        f"Videoni tomosha qilish uchun pastdagi tugmani bosing:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=video_detail_keyboard(video['url'], category_key),
        parse_mode="HTML",
        disable_web_page_preview=False
    )


@dp.callback_query(F.data == "lectures_list")
async def back_to_lectures_handler(callback):
    await callback.message.edit_text(
        "🎓 <b>ISLOMIY MA'RUZALAR VA VIDEOLAR</b>\n\n"
        "📺 Kategoriyani tanlang:",
        reply_markup=lectures_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("region_"))
async def select_region_handler(callback):
    user_id = callback.from_user.id
    region_name = callback.data.replace("region_", "")
    user_region[user_id] = region_name

    await callback.message.edit_text(
        f"✅ <b>{region_name}</b> tanlandi!\n\n"
        f"🏘️ <b>Tumanini tanlang:</b>",
        reply_markup=districts_keyboard(region_name),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("district_"))
async def select_district_handler(callback):
    user_id = callback.from_user.id
    data = callback.data.split("_", 1)
    region_name = data[1].split("_")[0]
    district = "_".join(data[1].split("_")[1:])

    user_district[user_id] = district

    await callback.message.edit_text(
        f"✅ <b>{district}</b> tanlandi!\n\n"
        f"📍 <b>Viloyat:</b> {region_name}\n"
        f"🏘️ <b>Tuman:</b> {district}",
        parse_mode="HTML"
    )
    await callback.message.answer("📋 <b>Menyu:</b>", reply_markup=main_menu(), parse_mode="HTML")


@dp.callback_query(F.data == "back_to_regions")
async def back_to_regions_handler(callback):
    await callback.message.edit_text("🌍 <b>Viloyatingizni tanlang:</b>", reply_markup=regions_keyboard(),
                                     parse_mode="HTML")


@dp.message(F.text == "📍 ENG YAQIN MASJIDNI TOPISH")
async def find_mosque_handler(message: Message):
    user_id = message.from_user.id

    if not await is_user_ready(user_id, message):
        return

    if user_id not in user_region:
        await message.answer("❌ <b>Avvalo viloyatni tanlang!</b>", reply_markup=regions_keyboard(), parse_mode="HTML")
        return

    await message.answer(
        "📍 <b>Eng yaqin masjidni topish uchun joylashuvingizni yuboring!</b>\n\n"
        "🗺️ Quyidagi tugmani bosib, joylashuvingizni yuboring:",
        reply_markup=location_request_keyboard(),
        parse_mode="HTML"
    )


@dp.message(F.text == "🕌 Bugungi namoz vaqtlari")
async def prayer_times_handler(message: Message):
    """YANGI - TEZ ISHLAYDI!"""
    user_id = message.from_user.id
    if not await is_user_ready(user_id, message):
        return
    if user_id not in user_region:
        await message.answer("Viloyat tanlang", reply_markup=regions_keyboard(), parse_mode="HTML")
        return

    region_name = user_region[user_id]
    city = REGIONS_WITH_DISTRICTS[region_name]['city']
    district = user_district.get(user_id, "")

    # Asinxron olish - TEZ!
    times = await get_prayer_times_async(city)
    if not times:
        await message.answer("❌ Xatolik yuz berdi", parse_mode="HTML")
        return

    text = f"📍 <b>{region_name}</b>\n🏘️ <b>{district}</b>\n\n📖 <b>Bugungi namoz vaqtlari:</b>\n\n🌅 <b>Bomdod:</b> {times['Fajr']}\n🌞 <b>Quyosh:</b> {times['Sunrise']}\n🕛 <b>Peshin:</b> {times['Dhuhr']}\n🕓 <b>Asr:</b> {times['Asr']}\n🌇 <b>Shom:</b> {times['Maghrib']}\n🌙 <b>Xufton:</b> {times['Isha']}"
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "🌙 Ro'za vaqtlari")
async def roza_times_handler(message: Message):
    """YANGI - TEZ ISHLAYDI!"""
    user_id = message.from_user.id
    if not await is_user_ready(user_id, message):
        return
    if user_id not in user_region:
        await message.answer("Viloyat tanlang", reply_markup=regions_keyboard(), parse_mode="HTML")
        return

    region_name = user_region[user_id]
    city = REGIONS_WITH_DISTRICTS[region_name]['city']
    district = user_district.get(user_id, "")

    # Asinxron olish - TEZ!
    times = await get_prayer_times_async(city)
    if not times:
        await message.answer("❌ Xatolik yuz berdi", parse_mode="HTML")
        return

    text = f"📍 <b>{region_name}</b>\n🏘️ <b>{district}</b>\n\n🌙 <b>Bugungi ro'za vaqtlari:</b>\n\n🥣 <b>Saharlik (Imsak):</b> {times['Fajr']}\n🍽 <b>Iftar:</b> {times['Maghrib']}"

    await message.answer(text, reply_markup=roza_duas_keyboard(), parse_mode="HTML")


@dp.callback_query(F.data.startswith("roza_dua_"))
async def roza_dua_handler(callback):
    dua_id = int(callback.data.split("_")[-1])
    dua = QURAN_DUAS_FULL.get(dua_id)
    if dua:
        text = f"<b>{dua['name']}</b>\n\n<b>📖 Arabcha:</b>\n{dua['arabic']}\n\n<b>🔤 Transliteratsiya:</b>\n{dua['transliteration']}\n\n<b>📝 Ma'nosi:</b>\n{dua['meaning']}\n\n<b>📚 Kategoriya:</b> {dua['category']}"
        await callback.message.answer(text, parse_mode="HTML")


@dp.message(F.text == "📿 QUR'ONDAGI DU'OLAR (25+)")
async def duas_handler(message: Message):
    user_id = message.from_user.id
    if not await is_user_ready(user_id, message):
        return
    await message.answer("📿 <b>Du'o kategoriyasini tanlang:</b>", reply_markup=duas_category_keyboard(),
                         parse_mode="HTML")


@dp.callback_query(F.data.startswith("cat_"))
async def category_handler(callback):
    category = callback.data.replace("cat_", "")
    await callback.message.edit_text(f"📿 <b>{category} Du'olari:</b>", reply_markup=duas_by_category_keyboard(category),
                                     parse_mode="HTML")


@dp.callback_query(F.data.startswith("dua_"))
async def dua_handler(callback):
    dua_id = int(callback.data.split("_")[1])
    dua = QURAN_DUAS_FULL.get(dua_id)
    if dua:
        text = f"<b>{dua['name']}</b>\n\n<b>📖 Arabcha:</b>\n{dua['arabic']}\n\n<b>🔤 Transliteratsiya:</b>\n{dua['transliteration']}\n\n<b>📝 Ma'nosi:</b>\n{dua['meaning']}\n\n<b>📚 Kategoriya:</b> {dua['category']}"
        await callback.message.answer(text, parse_mode="HTML")


@dp.callback_query(F.data == "duas_categories")
async def back_duas_categories_handler(callback):
    await callback.message.edit_text("📿 <b>Du'o kategoriyasini tanlang:</b>", reply_markup=duas_category_keyboard(),
                                     parse_mode="HTML")


@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback):
    await callback.message.answer("📋 <b>Asosiy Menyu:</b>", reply_markup=main_menu(), parse_mode="HTML")


@dp.message(F.text == "📅 7 kunlik jadval")
async def weekly_schedule_handler(message: Message):
    """YANGI - TEZ ISHLAYDI!"""
    user_id = message.from_user.id
    if not await is_user_ready(user_id, message):
        return
    if user_id not in user_region:
        await message.answer("Viloyat tanlang", reply_markup=regions_keyboard(), parse_mode="HTML")
        return

    region_name = user_region[user_id]
    city = REGIONS_WITH_DISTRICTS[region_name]['city']
    district = user_district.get(user_id, "")

    text = f"📅 <b>{region_name} - {district}</b> uchun 7 kunlik jadval:\n\n"

    # Parallel ravishda barcha kunlar uchun ma'lumot olish - JUDA TEZ!
    tasks = []
    for i in range(7):
        date = datetime.now() + timedelta(days=i)
        tasks.append(get_prayer_times_async(city, date))

    results = await asyncio.gather(*tasks)

    days_uz = {"Monday": "Dushanba", "Tuesday": "Seshanba", "Wednesday": "Chorshanba", "Thursday": "Payshanba",
               "Friday": "Juma", "Saturday": "Shanba", "Sunday": "Yakshanba"}

    for i, times in enumerate(results):
        if times:
            date = datetime.now() + timedelta(days=i)
            day_name = days_uz.get(date.strftime("%A"), "")
            text += f"<b>{date.strftime('%d.%m')} - {day_name}</b>\n🥣 {times['Fajr']} | 🕛 {times['Dhuhr']} | 🕓 {times['Asr']} | 🌇 {times['Maghrib']} | 🌙 {times['Isha']}\n\n"

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "🔁 Viloyatni o'zgartirish")
async def change_region_handler(message: Message):
    user_id = message.from_user.id
    if not await is_user_ready(user_id, message):
        return
    user_region.pop(user_id, None)
    user_district.pop(user_id, None)
    await message.answer("🌍 <b>Yangi viloyatni tanlang:</b>", reply_markup=regions_keyboard(), parse_mode="HTML")


# ============ BOT ISHGA TUSHIRISH ============
async def on_startup():
    logger.info("=" * 70)
    logger.info("🚀 BOT ISHGA TUSHYAPTI - QIBLA KOMPASI BILAN! ⚡🧭")
    logger.info(f"📍 Jami viloyat: {len(REGIONS_WITH_DISTRICTS)}")
    logger.info(f"🏘️ Jami tuman: {sum(len(r['districts']) for r in REGIONS_WITH_DISTRICTS.values())}")
    logger.info(f"🕌 Masjidlar: {sum(len(m) for m in MOSQUES.values())}")
    logger.info(f"🎓 Ma'ruza kategoriyalari: {len(LECTURE_CATEGORIES)}")
    logger.info(f"🧭 Qibla kompasi: FAOL")
    logger.info(f"🕋 Ka'ba koordinatalari: {KAABA_LAT}°, {KAABA_LON}°")
    logger.info(f"💾 Kesh faollashtirildi: Namoz vaqtlari va Videolar")
    logger.info("=" * 70)
    scheduler.start()


async def on_shutdown():
    logger.info("🛑 BOT TO'XTADI")
    scheduler.shutdown()


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        logger.info("⚠️ Bot to'xtatildi")
