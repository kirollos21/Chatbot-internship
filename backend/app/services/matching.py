"""Concept-level matching between a resident's question and a stored record.

Trigram similarity is character-level. It happily recognises `ghrama` and
`3'rama` as one word, but it has no idea that a resident's "dog" is the
dataset's "pets", or that "grass" is written there as "landscaped zones". Those
were the misses that made paraphrased questions escalate: the correct record was
retrieved and ranked first, then scored far too low to be used.

This module supplies the missing layer. A question is reduced to the *concepts*
it is about, and each concept carries every surface form it takes across
English, Arabic and Franco. A record matches a concept when it contains any of
those forms. **Coverage** — the share of the question's concepts that a record
accounts for, weighted by how discriminative each concept is — then measures how
well that record answers *this* question, independently of the words the
resident happened to choose.

Two deliberate exclusions keep coverage meaningful:

* Grammatical filler ("can I", "هل", "el") carries no topic.
* Qualifiers — "fine", "allowed", "hours", "phone" — are what the resident
  wants to *know*, not what the question is *about*, and `app.services.intent`
  already routes on them. Counting them here would penalise every violation
  record, because a violation's text states the act and never the word "fine".

A concept the corpus cannot match still counts in the denominator. That is the
point, not an oversight: it is how "what is the wifi password" scores low and
escalates, instead of inheriting the confidence of whatever it ranked first.

The concept table is curated against the shipped dataset's own vocabulary. It
decides *which record is about the question*; it never decides what the answer
says. Every word a resident reads still comes from the record itself.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from functools import lru_cache

from app.services.language import normalise_arabic, skeleton

# The apostrophe stays inside the token: it is what distinguishes the Franco
# digraphs 3'/6'/9' (غ/ظ/ض), and splitting on it destroys the marker. It also
# keeps English contractions whole.
_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)?", re.UNICODE)
_ARABIC_CHAR = re.compile(r"[؀-ۿ]")

# Grammatical filler. Removing it stops "what is the ... for ..." from diluting
# every question down to the same handful of shared words.
_STOPWORD_SOURCE = """
    a an the this that these those there here it its is are am was were be been being
    do does did done have has had having can could may might must shall should will would
    i me my mine we us our you your he she they them their his her
    of in on at to for from by with without within into onto over under about
    and or but if then than so as also very much many any all some no not none
    what which who whom whose where when why how whats what's
    please tell know need want get got give show say said thing something anything
    area areas zone zones place places location locations spot spots space spaces
    site sites part parts side thing case way point kind type sort
    مكان أماكن الأماكن منطقة مناطق المنطقة موقع مواقع جزء ناحية حالة نوع
    ok okay yes yeah no sure thanks thank hello hi hey
    el al ana enta enty ya wala aw fe fi men mn le li 3an 3ala da di de dah deh
    eh ezay ezzay leh lih keda kda momken mumkin lw law bas kol kul
    fel fil bel bil wel wil 3al 3a lel lil
    a3mel a3mal n3mel te3mel ye3mel 3amalt ha3mel
    هل ما ماذا من في على الى إلى عن مع او أو و ب ل ك ان أن إن هو هي هم انا أنا
    انت أنت احتاج أريد اريد عايز عاوز ممكن لو لكن كل بس ايه إيه ازاي إزاي ليه
    يوجد هناك هذا هذه ذلك التي الذي كان يكون يمكن اقدر أقدر عند لدي
    شكرا شكرًا مرحبا اهلا أهلا نعم لا
    """

# What the resident wants to know, as opposed to what they are asking about.
# Recognised so they are not mistaken for topic terms, then dropped: intent
# routing (`app.services.intent`) is what these belong to.
_QUALIFIER_SOURCE = """
    fine fines fined penalty penalties charge charged cost costs price amount egp pound pounds
    allowed allow allowable permitted permissible legal illegal prohibited forbidden banned
    rule rules rulebook regulation regulations policy policies law laws
    hour hours time times timing schedule open opens opening close closes closing closed
    phone telephone number numbers contact contacts call hotline whatsapp
    report complain complaint escalate
    غرامة الغرامة غرامات عقوبة عقوبات جنيه مبلغ كام تكلفة سعر
    مسموح يسمح ممنوع محظور مخالفة المخالفة مخالفات جائز يجوز ينفع قانوني
    لائحة اللائحة لوائح قانون قواعد نظام
    مواعيد ساعات وقت يفتح يقفل متى الميعاد
    رقم أرقام ارقام تليفون هاتف اتصال ساخن
    بلاغ ابلاغ أبلاغ شكوى اشتكي أشتكي
    ghrama gharama ghrma mokhalfa mukhalfa 3oqoba masmoo7 masmouh mamnoo3 mamnou3
    mw3ad mawa3eed ra2m raqm telefon shakwa kam kaam feen fen emta la2e7a qanoon
    """

# Franco qualifier spellings. Unlike the lists above these also contribute
# consonant skeletons, so every Franco spelling of "fine" is recognised rather
# than only the handful written out here.
_FRANCO_QUALIFIER_SOURCE = """
    ghrama gharama ghrma 3'rama 3'arama
    mokhalfa mukhalfa
    masmoo7 masmouh masmo7 mamnoo3 mamnou3 mamno3
    shakwa shakwet
    """


# --- concept table ------------------------------------------------------
# One entry per topic a resident can ask about. `en`/`ar` are surface forms
# matched against the record text; `franco` entries are matched on their
# consonant skeleton, so spelling variants converge without being listed.
#
# Each group holds the *dataset's* wording alongside the wording a resident is
# likely to use — that pairing is the whole point. "grass" is what residents
# write; "landscaped" is what the regulations say.
_CONCEPT_TABLE: dict[str, dict[str, list[str]]] = {
    "pet": {
        "en": ["pet", "pets", "animal", "animals", "dog", "dogs", "puppy", "cat", "cats",
               "kitten", "bird", "birds", "livestock"],
        "ar": ["حيوان", "حيوانات", "الحيوانات", "كلب", "كلاب", "الكلاب", "قطة", "قطط", "قط",
               "طيور", "طائر", "أليف", "أليفة", "اليفة", "الأليفة"],
        "franco": ["hayawan", "kalb", "kalb", "kelab", "3otta", "qotta"],
    },
    "accompany": {
        "en": ["accompany", "accompanied", "accompanying", "bring", "bringing", "brought",
               "take", "taking", "enter", "entering", "admit", "admitting", "admission",
               "introduce", "introducing", "with"],
        "ar": ["اصطحاب", "باصطحاب", "يصطحب", "إدخال", "ادخال", "يدخل", "دخول", "جلب", "معه"],
        "franco": ["estes7ab", "yedakhal", "edkhal", "gayeb"],
    },
    "leash": {
        "en": ["leash", "leashed", "muzzle", "muzzled", "collar", "restrain", "restrained"],
        "ar": ["سلسلة", "رباط", "كمامة", "مقود"],
        "franco": ["selsela", "kmama", "kemama"],
    },
    "vaccination": {
        "en": ["vaccination", "vaccinations", "vaccinated", "vaccine", "immunisation", "veterinary"],
        "ar": ["تطعيم", "تطعيمات", "مطعم", "بيطري", "بيطرية"],
        "franco": ["tat3eem", "bitari"],
    },
    "landscape": {
        "en": ["grass", "grassed", "lawn", "landscaped", "landscaping", "landscape", "garden",
               "gardens", "green", "greenery", "plant", "plants", "planting", "planted",
               "tree", "trees", "shrub", "shrubs", "flowerbed", "turf", "vegetation"],
        "ar": ["زرع", "الزرع", "زراعة", "زراعات", "الزراعات", "الزراع", "حديقة", "حدائق",
               "الحديقة", "الحدائق", "مسطحات", "المسطحات", "خضراء", "نجيل", "أشجار",
               "اشجار", "شجرة", "نباتات", "مزروعات", "جنينة"],
        "franco": ["zar3", "zara3", "gnena", "genena", "hadiqa", "shagar", "nageel"],
    },
    "vehicle": {
        "en": ["vehicle", "vehicles", "car", "cars", "parking", "park", "parked", "parks",
               "garage", "driveway", "motorbike", "motorcycle", "truck", "lorry", "bus"],
        "ar": ["سيارة", "سيارات", "عربية", "عربيات", "مركبة", "مركبات", "ركن", "الركنة",
               "انتظار", "جراج", "الجراج", "موتوسيكل", "شاحنة", "أتوبيس"],
        "franco": ["3arabeya", "3arabiya", "sayara", "markaba", "rakna", "rekna", "garage",
                   "motosikl"],
    },
    "sidewalk": {
        "en": ["sidewalk", "sidewalks", "pavement", "kerb", "curb", "walkway", "footpath"],
        "ar": ["رصيف", "أرصفة", "ارصفة", "الرصيف", "ممشى"],
        "franco": ["raseef", "rasif"],
    },
    "speed": {
        "en": ["speed", "speeding", "overspeeding", "fast", "drive", "driving", "driver",
               "reckless", "racing"],
        "ar": ["سرعة", "السرعة", "مسرع", "قيادة", "يقود", "تهور", "سباق"],
        "franco": ["sor3a", "sur3a", "qiyada", "sewaqa"],
    },
    "licence": {
        "en": ["licence", "licences", "license", "licensed", "unlicensed", "plate", "plates",
               "registration"],
        "ar": ["رخصة", "رخص", "مرخص", "مرخصة", "لوحة", "لوحات", "ترخيص"],
        "franco": ["rokhsa", "rukhsa", "tarkhees"],
    },
    "buggy": {
        "en": ["golf", "cart", "carts", "buggy", "buggies", "caravan", "atv", "quad", "scooter",
               "bicycle", "bike", "bikes"],
        "ar": ["جولف", "عربة", "باجي", "كرافان", "دراجة", "دراجات", "سكوتر"],
        "franco": ["bagy", "baggy", "karavan", "daraga", "3agala"],
    },
    "beach": {
        "en": ["beach", "beaches", "shore", "shoreline", "seaside", "sea", "sand", "sahel",
               "coast", "coastal"],
        "ar": ["شاطئ", "الشاطئ", "شواطئ", "ساحل", "الساحل", "الشمالي", "بحر", "البحر", "رمل"],
        "franco": ["shate2", "shati", "sahel", "sa7el", "ba7r", "bahr"],
    },
    "lagoon": {
        "en": ["lagoon", "lagoons", "lake", "lakes"],
        "ar": ["بحيرة", "البحيرة", "بحيرات", "البحيرات"],
        "franco": ["bo7ayra", "buhayra"],
    },
    "pool": {
        "en": ["pool", "pools", "swim", "swimming", "swimmer", "swimmers", "dive", "diving"],
        "ar": ["حمام", "السباحة", "حمامات", "مسبح", "المسبح", "سباحة", "غطس"],
        "franco": ["masba7", "masbah", "sebaha", "seba7a", "7ammam"],
    },
    "sunbed": {
        "en": ["sunbed", "sunbeds", "lounger", "loungers", "deckchair", "umbrella", "umbrellas",
               "parasol", "reserve", "reserving", "reserved", "towel"],
        "ar": ["شازلونج", "كرسي", "كراسي", "مظلة", "شمسية", "حجز", "يحجز", "فوطة"],
        "franco": ["shazlong", "shezlong", "kursi", "7agz", "hagz"],
    },
    "swimwear": {
        "en": ["swimwear", "swimsuit", "swimsuits", "costume", "trunks", "diaper", "diapers",
               "attire", "clothing", "clothes", "dress"],
        "ar": ["مايوه", "المايوه", "ملابس", "حفاضة", "حفاضات", "زي", "لبس"],
        "franco": ["mayoh", "mayo", "hafada", "labs", "hodoom"],
    },
    "lifeguard": {
        "en": ["lifeguard", "lifeguards", "rescue", "rescuer", "supervision", "supervisor",
               "supervised", "unsupervised"],
        "ar": ["إنقاذ", "الإنقاذ", "الانقاذ", "منقذ", "منقذين", "إشراف", "اشراف", "مراقبة"],
        "franco": ["monqez", "munqiz", "enqaz", "eshraf"],
    },
    "cabin": {
        "en": ["cabin", "cabins", "cabana", "cabanas", "chalet", "chalets", "kiosk"],
        "ar": ["كابينة", "كابينه", "كبائن", "الكبائن", "شاليه", "شاليهات"],
        "franco": ["kabina", "kabayen", "shalet", "shale"],
    },
    "waste": {
        "en": ["waste", "wastes", "garbage", "rubbish", "trash", "refuse", "litter", "littering",
               "dump", "dumping", "dispose", "disposal", "disposing", "discard", "discarding",
               "throw", "throwing", "bin", "bins"],
        "ar": ["قمامة", "القمامة", "مخلفات", "المخلفات", "زبالة", "نفايات", "إلقاء", "القاء",
               "تخلص", "رمي", "يرمي", "صندوق"],
        "franco": ["zebala", "zbala", "qomama", "mokhalafat", "elqa2", "ramy"],
    },
    "debris": {
        "en": ["debris", "rubble", "finishing", "leftover"],
        "ar": ["أنقاض", "انقاض", "مخلفات", "تشطيب", "التشطيب", "تشطيبات"],
        "franco": ["angad", "anqad", "tashteeb", "tashtib"],
    },
    "construction": {
        "en": ["build", "builds", "building", "built", "construct", "construction",
               "material", "materials", "cement", "brick", "bricks", "scaffolding",
               "storing", "stored", "storage"],
        "ar": ["بناء", "البناء", "إنشاءات", "انشاءات", "مواد", "المواد", "أسمنت", "اسمنت",
               "طوب", "تخزين", "سقالة"],
        "franco": ["benaa", "bena", "asmant", "toob", "takhzeen", "mawad"],
    },
    "burning": {
        "en": ["burn", "burning", "burnt", "fire", "fires", "bonfire", "flame", "flames",
               "ignite", "igniting", "lighting"],
        "ar": ["حرق", "الحرق", "إشعال", "اشعال", "نار", "النار", "حرائق", "شعلة", "لهب"],
        "franco": ["7arq", "harq", "nar", "esh3al"],
    },
    "noise": {
        "en": ["noise", "noises", "noisy", "loud", "loudly", "sound", "sounds", "music",
               "speaker", "speakers", "shouting", "disturbance", "disturbing", "quiet"],
        "ar": ["ضوضاء", "الضوضاء", "إزعاج", "ازعاج", "صوت", "أصوات", "عالي", "موسيقى",
               "سماعة", "صراخ", "هدوء"],
        "franco": ["dawdaa", "dawda", "ez3ag", "sot", "sowt", "musiqa", "3ali"],
    },
    "party": {
        "en": ["party", "parties", "gathering", "gatherings", "celebration", "celebrations",
               "event", "events", "wedding", "guest", "guests", "crowd"],
        "ar": ["حفلة", "حفلات", "حفل", "تجمع", "تجمعات", "مناسبة", "زفاف", "ضيوف", "ضيف"],
        "franco": ["7afla", "hafla", "tagamo3", "monasba", "dyoof"],
    },
    "fireworks": {
        "en": ["firework", "fireworks", "firecracker", "firecrackers", "flare", "flares"],
        "ar": ["ألعاب", "نارية", "شماريخ", "صواريخ", "بمب"],
        "franco": ["shamarikh", "al3ab nareya"],
    },
    "barbecue": {
        "en": ["barbecue", "barbecues", "bbq", "grill", "grilling", "shisha", "hookah",
               "hubbly", "charcoal", "smoke", "smoking", "cigarette"],
        "ar": ["شواء", "الشواء", "منقل", "شيشة", "الشيشة", "فحم", "تدخين", "سيجارة"],
        "franco": ["shewa", "mangal", "shisha", "fa7m", "tadkheen"],
    },
    "generator": {
        "en": ["generator", "generators", "electricity", "electrical", "power", "wiring", "cable"],
        "ar": ["مولد", "مولدات", "كهرباء", "كهربائي", "أسلاك", "كابل"],
        "franco": ["mowaled", "kahraba"],
    },
    "pergola": {
        "en": ["pergola", "pergolas", "awning", "awnings", "canopy", "shade", "shading",
               "gazebo", "trellis"],
        "ar": ["برجولة", "برجولات", "البرجولة", "مظلة", "مظلات", "تظليل", "سترة"],
        "franco": ["bargola", "brgola", "bargula", "mazalla", "tazleel"],
    },
    "facade": {
        "en": ["facade", "facades", "façade", "exterior", "external", "elevation", "elevations",
               "appearance", "outside", "wall", "walls"],
        "ar": ["واجهة", "الواجهة", "واجهات", "خارجي", "الخارجي", "المظهر", "حائط", "جدار"],
        "franco": ["wagha", "wag-ha", "khargi", "mazhar"],
    },
    "paint": {
        "en": ["paint", "paints", "painting", "painted", "repaint", "colour", "colours",
               "color", "colors", "coating"],
        "ar": ["دهان", "دهانات", "الدهان", "طلاء", "لون", "ألوان", "الوان"],
        "franco": ["dohan", "dehan", "tela", "lon", "loon"],
    },
    "modification": {
        "en": ["modification", "modifications", "modify", "modified", "alter", "alteration",
               "alterations", "change", "changes", "renovate", "remodel", "extension",
               "extend", "demolish", "demolition", "install", "installing", "installation"],
        "ar": ["تعديل", "تعديلات", "التعديل", "تغيير", "ترميم", "توسيع", "هدم", "تركيب",
               "تركيبات", "إنشاء", "انشاء"],
        "franco": ["ta3deel", "taghyeer", "tarkeeb", "tawsee3", "hadm"],
    },
    "permit": {
        "en": ["permit", "permits", "permission", "permissions", "approval", "approvals",
               "approved", "authorisation", "authorization", "authorised", "authorized",
               "consent", "unauthorized", "unauthorised", "prior"],
        "ar": ["تصريح", "تصاريح", "التصريح", "موافقة", "موافقات", "إذن", "اذن", "ترخيص",
               "بدون", "مسبق", "مسبقة"],
        "franco": ["tasree7", "tasreeh", "muwafqa", "mowafqa", "ezn", "bedoon"],
    },
    "jacuzzi": {
        "en": ["jacuzzi", "jacuzzis", "hottub", "tub", "spa", "sauna"],
        "ar": ["جاكوزي", "الجاكوزي", "ساونا"],
        "franco": ["jakuzi", "gakuzi"],
    },
    "satellite": {
        "en": ["satellite", "satellites", "dish", "dishes", "antenna", "antennas", "aerial",
               "receiver"],
        "ar": ["ستالايت", "دش", "الدش", "أطباق", "هوائي", "رسيفر"],
        "franco": ["dish", "satalayt", "hawaii"],
    },
    "solar": {
        "en": ["solar", "heater", "heaters", "boiler", "panel", "panels"],
        "ar": ["شمسي", "شمسية", "سخان", "سخانات", "ألواح", "الواح"],
        "franco": ["sakhan", "sakhkhan", "shamsi"],
    },
    "camera": {
        "en": ["camera", "cameras", "cctv", "surveillance", "monitoring", "recording", "privacy"],
        "ar": ["كاميرا", "كاميرات", "مراقبة", "المراقبة", "تصوير", "خصوصية"],
        "franco": ["kamera", "kamira", "muraqaba", "tasweer"],
    },
    "airconditioner": {
        "en": ["air", "conditioner", "conditioners", "conditioning", "ac", "aircon", "split",
               "condenser", "unit", "hvac", "compressor"],
        "ar": ["تكييف", "التكييف", "تكييفات", "مكيف", "مكيفات", "كومبروسر", "وحدة"],
        "franco": ["takyeef", "takeef", "mokayef", "kondensar"],
    },
    "balcony": {
        "en": ["balcony", "balconies", "terrace", "terraces", "roof", "rooftop", "veranda",
               "loggia"],
        "ar": ["بلكونة", "بلكونات", "شرفة", "شرفات", "تراس", "سطح", "السطح", "الروف"],
        "franco": ["balakona", "balkona", "sharfa", "sat7", "satah", "teras"],
    },
    "elevator": {
        "en": ["elevator", "elevators", "lift", "lifts", "escalator"],
        "ar": ["مصعد", "المصعد", "مصاعد", "المصاعد", "أسانسير", "اسانسير"],
        "franco": ["masaad", "mas3ad", "asanser", "asansir"],
    },
    "worker": {
        "en": ["worker", "workers", "labour", "labourer", "labor", "laborer", "staff",
               "contractor", "contractors", "technician", "workshop", "workshops", "crew"],
        "ar": ["عامل", "عمال", "العمال", "عاملين", "ورشة", "ورش", "مقاول", "مقاولين", "فني"],
        "franco": ["3ommal", "3amel", "warsha", "moqawel", "fanni"],
    },
    "domestic": {
        "en": ["nanny", "maid", "housekeeper", "driver", "servant", "domestic", "helper"],
        "ar": ["خدم", "خادمة", "شغالة", "مربية", "سواق", "سائق"],
        "franco": ["shaghala", "morabya", "sawa2", "sayes"],
    },
    "rent": {
        "en": ["rent", "rents", "rental", "rentals", "renting", "rented", "lease", "leases",
               "leasing", "leased", "sublease", "sublet", "subletting", "tenant", "tenants",
               "landlord", "airbnb", "shortterm", "short term", "short-term", "daily rental",
               "holiday rental"],
        "ar": ["إيجار", "ايجار", "الإيجار", "تأجير", "تاجير", "مؤجر", "مستأجر", "الباطن",
               "إيجارات", "مالك"],
        "franco": ["eegar", "egar", "ta2geer", "tageer", "musta2ger", "el batn", "malek"],
    },
    "signage": {
        "en": ["sign", "signs", "signage", "signboard", "advertisement", "advertisements",
               "advertising", "advertise", "banner", "banners", "board", "boards", "poster",
               "sticker", "stickers", "logo"],
        "ar": ["لافتة", "لافتات", "إعلان", "اعلان", "إعلانات", "لوحة", "لوحات", "ملصق",
               "ملصقات", "بوستر"],
        "franco": ["lafta", "e3lan", "lo7a", "molsaq", "steker"],
    },
    "commercial": {
        "en": ["commercial", "commerce", "business", "businesses", "shop", "shops", "store",
               "office", "offices", "clinic", "clinics", "nursery", "salon", "trade", "trading",
               "sell", "selling", "sale"],
        "ar": ["تجاري", "تجارية", "نشاط", "محل", "محلات", "مكتب", "مكاتب", "عيادة", "عيادات",
               "حضانة", "صالون", "بيع", "تجارة"],
        "franco": ["togari", "tegara", "ma7al", "maktab", "3eyada", "hadana", "bee3"],
    },
    "playground": {
        "en": ["playground", "playgrounds", "playarea", "play", "slide", "slides", "swing",
               "swings", "seesaw", "trampoline", "sandpit"],
        "ar": ["ألعاب", "الألعاب", "العاب", "ملعب", "ملاعب", "زحليقة", "مرجيحة", "نطاطية"],
        "franco": ["mal3ab", "al3ab", "zahlaqa", "margee7a"],
    },
    "gym": {
        "en": ["gym", "gyms", "gymnasium", "fitness", "court", "courts", "pitch", "sport",
               "sports", "football", "tennis", "padel", "basketball", "exercise", "training"],
        "ar": ["جيم", "الجيم", "صالة", "الرياضية", "رياضة", "ملعب", "ملاعب", "كورت",
               "تنس", "بادل", "كرة", "تمرين"],
        "franco": ["gym", "sala", "reyada", "kort", "tenes", "padel", "korat"],
    },
    "children": {
        "en": ["child", "children", "kid", "kids", "minor", "minors", "toddler", "infant",
               "baby", "babies", "age", "aged", "years", "adult", "adults", "accompanied",
               "accompanying", "supervision"],
        "ar": ["طفل", "أطفال", "اطفال", "الأطفال", "ولد", "أولاد", "اولاد", "سن", "عمر",
               "سنة", "سنوات", "بالغ", "بالغين", "مرافق", "مصاحبة"],
        "franco": ["tefl", "atfal", "welad", "sen", "3omr", "balegh", "morafeq"],
    },
    "gate": {
        "en": ["gate", "gates", "gatehouse", "entrance", "entrances", "entry", "exit", "access",
               "barrier", "checkpoint", "obstruct", "obstructing", "block", "blocking"],
        "ar": ["بوابة", "البوابة", "بوابات", "مدخل", "مداخل", "دخول", "خروج", "حاجز",
               "إعاقة", "اعاقة", "عرقلة", "سد"],
        "franco": ["bawaba", "madkhal", "dokhool", "khorog", "e3aqa"],
    },
    "visitor": {
        "en": ["visitor", "visitors", "guest", "guests", "delivery", "courier", "stranger",
               "outsider", "nonresident"],
        "ar": ["زائر", "زوار", "الزوار", "ضيف", "ضيوف", "الضيوف", "توصيل", "دليفري", "غريب"],
        "franco": ["za2er", "zowar", "deef", "dyoof", "delivery", "tawseel"],
    },
    "security": {
        "en": ["security", "guard", "guards", "patrol", "patrols", "watchman", "safety"],
        "ar": ["أمن", "الأمن", "امن", "حراسة", "حارس", "حراس", "دورية", "سلامة"],
        "franco": ["7erasa", "herasa", "hares", "salama"],
    },
    "maintenance": {
        "en": ["maintenance", "maintain", "maintaining", "repair", "repairs", "repairing",
               "fix", "fixing", "broken", "fault", "faulty", "defect", "service", "servicing"],
        "ar": ["صيانة", "الصيانة", "إصلاح", "اصلاح", "تصليح", "عطل", "معطل", "خدمة", "تالف"],
        "franco": ["seyana", "syana", "esla7", "tasleeh", "3atal"],
    },
    "water": {
        "en": ["water", "leak", "leaks", "leakage", "leaking", "drain", "drains", "drainage",
               "sewage", "sewer", "plumbing", "pipe", "pipes", "flood", "flooding", "shaft"],
        "ar": ["مياه", "المياه", "ماء", "تسريب", "تسرب", "صرف", "الصرف", "مجاري", "مواسير",
               "ماسورة", "غرق", "منور"],
        "franco": ["maya", "mayya", "tasreeb", "sarf", "magary", "masoora", "manwar"],
    },
    "unit": {
        "en": ["unit", "units", "apartment", "apartments", "flat", "flats", "villa", "villas",
               "townhouse", "duplex", "home", "house", "property", "residence", "residential",
               "premises", "boundary", "boundaries"],
        "ar": ["وحدة", "الوحدة", "وحدات", "شقة", "شقق", "فيلا", "فيلات", "منزل", "بيت",
               "عقار", "سكني", "سكنية", "حدود"],
        "franco": ["we7da", "shaqqa", "villa", "manzel", "bet", "3aqar", "sakani", "7odood"],
    },
    "vandalism": {
        "en": ["vandalism", "vandalise", "vandalize", "vandalizing", "damage", "damages",
               "damaging", "tamper", "tampering", "destroy", "destruction", "deface", "graffiti",
               "break", "breaking"],
        "ar": ["تخريب", "التخريب", "تلف", "إتلاف", "اتلاف", "عبث", "تدمير", "كسر", "تشويه"],
        "franco": ["takhreeb", "talaf", "3abas", "tadmeer", "kasr"],
    },
    "assault": {
        "en": ["assault", "assaulting", "attack", "attacking", "fight", "fighting", "abuse",
               "abusive", "harass", "harassment", "threaten", "insult", "misconduct"],
        "ar": ["اعتداء", "الاعتداء", "تعدي", "هجوم", "ضرب", "مشاجرة", "إساءة", "اساءة",
               "تهديد", "سب", "تحرش"],
        "franco": ["e3teda", "darb", "moshagra", "esa2a", "tahdeed", "ta7arosh"],
    },
    "qrcode": {
        "en": ["qr", "code", "codes", "barcode", "scan", "scanning", "tag", "tags", "pass",
               "passes", "permit", "card", "cards", "id", "identification"],
        "ar": ["كود", "أكواد", "اكواد", "باركود", "مسح", "تاج", "تصريح", "كارت", "بطاقة", "هوية"],
        "franco": ["kod", "akwad", "barkod", "kart", "betaqa", "haweya"],
    },
    "management": {
        "en": ["management", "manager", "administration", "administrative", "authority",
               "owner", "association", "committee", "board", "office"],
        "ar": ["إدارة", "الإدارة", "ادارة", "مدير", "المجتمعات", "جهة", "مالك", "اتحاد",
               "لجنة", "مكتب"],
        "franco": ["edara", "modeer", "mogtama3", "malek", "etehad", "lagna"],
    },
}


@dataclass(frozen=True)
class Concept:
    """A topic and every way a resident or the dataset might write it."""

    name: str
    single: frozenset[str]      # one-word forms, matched on tokens/stems
    phrases: tuple[str, ...]    # multi-word forms, matched as substrings
    skeletons: frozenset[str]   # Franco consonant skeletons
    substrings: frozenset[str]  # long forms, matched inside the record text

    @property
    def is_literal(self) -> bool:
        """A word with no entry in the table — kept verbatim so it still counts."""
        return self.name.startswith("literal:")


# --- normalisation ------------------------------------------------------

def _fold(text: str) -> str:
    return normalise_arabic((text or "").lower())


def _sk(token: str) -> str:
    """Franco consonant skeleton with the Egyptian ج folded to one symbol.

    ج romanises as both `g` (`gnena`) and `j` (`brjola`). Left unfolded, two
    spellings of the same word produce two different skeletons and never meet.
    """
    return skeleton(token).replace("j", "g")


# Two consonants is enough: an Arabic triliteral root loses its vowels and often
# reduces to exactly that (`zar3` -> `zr`), so a higher floor would discard the
# short domain words that matter most.
_MIN_SKELETON = 2


@lru_cache(maxsize=1)
def _drop() -> tuple[frozenset[str], frozenset[str]]:
    """(forms, skeletons) to ignore - grammatical filler and qualifiers alike.

    Folded and morphologically expanded here rather than written out above, so
    the source lists stay readable while still matching what the tokeniser
    actually produces.
    """
    forms: set[str] = set()
    skeletons: set[str] = set()

    # English and Arabic filler is matched on its own forms. Skeletonising it
    # would be actively harmful: an English word's consonants collide freely
    # with unrelated Franco topics ("short" and "cart" are both `crt`).
    for word in (_STOPWORD_SOURCE + " " + _QUALIFIER_SOURCE).split():
        folded = _fold(word)
        if folded:
            forms |= _expand(folded)

    for word in _FRANCO_QUALIFIER_SOURCE.split():
        folded = _fold(word)
        if not folded:
            continue
        forms |= _expand(folded)
        sk = _sk(folded)
        if len(sk) >= _MIN_SKELETON:
            skeletons.add(sk)

    return frozenset(forms), frozenset(skeletons)


def _en_stem(token: str) -> str:
    """Crude, deliberate: enough to fold `pets`->`pet` and `gardens`->`garden`.

    A real stemmer would be overkill — the concept table already lists the
    inflections that matter, and this only has to catch the ones it misses.
    """
    word = token
    if word.endswith("'s"):
        word = word[:-2]
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes")):
        return word[:-2]
    if len(word) > 4 and word.endswith("es") and not word.endswith("ees"):
        return word[:-1]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    if len(word) > 5 and word.endswith("ing"):
        return word[:-3]
    return word


def _ar_variants(token: str) -> set[str]:
    """Arabic clitics that change the surface form but not the word.

    `الزرع` and `زرع` are the same word; the definite article and the common
    single-letter prefixes are stripped so one matches the other.
    """
    out = {token}
    if len(token) > 4 and token.startswith("ال"):
        out.add(token[2:])
    if len(token) > 5 and token[0] in "وفبكل" and token[1:3] == "ال":
        out.add(token[3:])
    elif len(token) > 4 and token[0] in "وفبكل":
        out.add(token[1:])
    for suffix in ("ات", "ين", "ون", "ها", "هم"):
        if len(token) > 4 and token.endswith(suffix):
            out.add(token[: -len(suffix)])
    return out


def _expand(token: str) -> set[str]:
    """Every form of a single token that should be considered equivalent."""
    forms = {token}
    if _ARABIC_CHAR.search(token):
        forms |= _ar_variants(token)
    else:
        forms.add(_en_stem(token))
    return {f for f in forms if f}


@lru_cache(maxsize=1)
def _index() -> tuple[tuple[Concept, ...], dict[str, str], dict[str, str]]:
    """(concepts, single-form -> name, skeleton -> name)."""
    concepts: list[Concept] = []
    by_form: dict[str, str] = {}
    by_skeleton: dict[str, str] = {}

    for name, bank in _CONCEPT_TABLE.items():
        singles: set[str] = set()
        phrases: list[str] = []
        skeletons: set[str] = set()

        for form in bank.get("en", []) + bank.get("ar", []):
            folded = _fold(form).strip()
            if not folded:
                continue
            if " " in folded:
                phrases.append(folded)
                continue
            singles |= _expand(folded)

        for form in bank.get("franco", []):
            for part in _fold(form).split():
                sk = _sk(part)
                if len(sk) >= _MIN_SKELETON:
                    skeletons.add(sk)

        # Substring fallback for the morphology not modelled explicitly: Arabic
        # broken plurals and attached clitics, English compounds. The length
        # floors keep it from firing by accident - "car" inside "carpet".
        substrings = {
            f for f in singles
            if len(f) >= (4 if _ARABIC_CHAR.search(f) else 6)
        }

        concepts.append(
            Concept(
                name,
                frozenset(singles),
                tuple(phrases),
                frozenset(skeletons),
                frozenset(substrings),
            )
        )
        # First writer wins: a form shared by two concepts (e.g. "unit") keeps
        # the earlier, more specific topic rather than silently flipping.
        for single in singles:
            by_form.setdefault(single, name)
        for sk in skeletons:
            by_skeleton.setdefault(sk, name)

    return tuple(concepts), by_form, by_skeleton


# --- the record side ---------------------------------------------------

@dataclass(frozen=True)
class RecordIndex:
    tokens: frozenset[str]
    text: str
    skeletons: frozenset[str]


@lru_cache(maxsize=4096)
def build_record_index(search_text: str) -> RecordIndex:
    """Searchable form of one record.

    Cached because the same few hundred record texts are re-scored on every
    single request; without it this would refold the whole corpus each time.
    """
    folded = _fold(search_text)
    tokens: set[str] = set()
    skeletons: set[str] = set()
    for token in _WORD.findall(folded):
        tokens |= _expand(token)
        if not _ARABIC_CHAR.search(token):
            sk = _sk(token)
            if len(sk) >= _MIN_SKELETON:
                skeletons.add(sk)
    return RecordIndex(frozenset(tokens), folded, frozenset(skeletons))


def topic_skeletons() -> frozenset[str]:
    """Every consonant skeleton the concept table claims.

    Exposed so a test can assert the filler skeletons stay disjoint from it: an
    overlap would silently discard a real topic as filler.
    """
    _, _, by_skeleton = _index()
    return frozenset(by_skeleton)


def concept_matches(concept: Concept, index: RecordIndex) -> bool:
    if concept.single & index.tokens:
        return True
    if concept.skeletons & index.skeletons:
        return True
    if any(phrase in index.text for phrase in concept.phrases):
        return True
    return any(form in index.text for form in concept.substrings)


# --- the query side ----------------------------------------------------

def extract_concepts(query: str) -> list[Concept]:
    """The topics a question is about, in the order they appear.

    Filler and qualifier words are dropped; an unrecognised word is kept as a
    literal concept so that asking about something outside the dataset lowers
    the score instead of being silently ignored.
    """
    folded = _fold(query)
    concepts, by_form, by_skeleton = _index()
    by_name = {c.name: c for c in concepts}

    found: list[Concept] = []
    seen: set[str] = set()

    def add(concept: Concept) -> None:
        if concept.name not in seen:
            seen.add(concept.name)
            found.append(concept)

    # Multi-word forms first: "air conditioner" must not be read as two
    # unrelated words, one of which ("air") is meaningless on its own.
    consumed = folded
    for concept in concepts:
        for phrase in concept.phrases:
            if phrase in consumed:
                add(concept)
                consumed = consumed.replace(phrase, " ")

    drop_forms, drop_skeletons = _drop()

    for token in _WORD.findall(consumed):
        if len(token) < 2 or token.isdigit():
            continue

        forms = _expand(token)
        # Exact spelling first - the one check that cannot collide.
        if forms & drop_forms:
            continue

        sk = "" if _ARABIC_CHAR.search(token) else _sk(token)
        name = next((by_form[f] for f in forms if f in by_form), None)
        if name is None and len(sk) >= _MIN_SKELETON:
            name = by_skeleton.get(sk)

        if name is not None:
            add(by_name[name])
            continue

        # Only now: a Franco spelling of a qualifier ("3'rama" for "fine") that
        # no concept claimed. Checked last so a real topic sharing the same
        # consonant root is never discarded as filler.
        if sk and sk in drop_skeletons:
            continue

        # Unknown word: kept, matched on its own forms and skeleton. The floor
        # is higher here - a two-letter skeleton from a word that is not in the
        # table is far more likely to be a coincidence than a domain term.
        add(
            Concept(
                f"literal:{token}",
                frozenset(forms),
                (),
                frozenset({sk}) if len(sk) >= 4 else frozenset(),
                frozenset(
                    f for f in forms
                    if len(f) >= (4 if _ARABIC_CHAR.search(f) else 6)
                ),
            )
        )

    return found


# --- scoring -----------------------------------------------------------

def concept_weights(
    concepts: list[Concept], indexes: list[RecordIndex]
) -> dict[str, float]:
    """Inverse document frequency per concept, over the candidate set.

    A concept that nearly every record mentions says little about which record
    is the right one; a rare one says a great deal. A concept no record matches
    at all gets the highest weight and can never be satisfied — that is what
    makes an out-of-scope question score low rather than latch onto whatever
    happened to rank first.
    """
    total = len(indexes)
    if not total:
        return {c.name: 1.0 for c in concepts}
    weights: dict[str, float] = {}
    for concept in concepts:
        df = sum(1 for index in indexes if concept_matches(concept, index))
        weights[concept.name] = math.log(1.0 + total / (1.0 + df))
    return weights


def coverage(
    concepts: list[Concept], index: RecordIndex, weights: dict[str, float]
) -> float:
    """Weighted share of the question's concepts that this record accounts for."""
    if not concepts:
        return 0.0
    total = sum(weights.get(c.name, 1.0) for c in concepts)
    if total <= 0:
        return 0.0
    hit = sum(
        weights.get(c.name, 1.0)
        for c in concepts
        if concept_matches(c, index)
    )
    return round(hit / total, 4)
