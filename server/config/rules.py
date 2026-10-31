"""Business rules and thresholds. Every number the app decides with lives here, not in code."""

ENTRY_CATEGORIES = ["sowing", "seed", "land_prep", "fertiliser", "pesticide", "labour",
                    "irrigation", "harvest", "sale", "note"]
UNITS = ["kg", "bag", "quintal", "litre", "hour", "day", "acre", "none"]
CROPS = ["paddy", "wheat", "tomato", "other"]
EVENT_TYPES = ["hail", "inundation", "cloudburst", "landslide", "natural_fire",
               "unseasonal_rain_post_harvest", "other"]
EVENT_STATUSES = ["suspected", "confirmed", "dismissed"]
VISION_TAGS = ["healthy", "pest_damage", "waterlogging", "lodging", "unclear"]
NON_COST_CATEGORIES = {"sale", "harvest"}

# L4 crop calendar: stage -> inclusive day range from sowing/transplanting. None = open-ended.
CROP_CALENDAR = {
    "paddy": [("vegetative", 0, 59), ("flowering", 60, 89), ("maturity", 90, 119), ("harvest_ready", 120, None)],
    "wheat": [("vegetative", 0, 59), ("flowering", 60, 94), ("maturity", 95, 124), ("harvest_ready", 125, None)],
    "tomato": [("vegetative", 0, 34), ("flowering", 35, 59), ("fruiting", 60, 99), ("harvest_ready", 100, None)],
}
SENSITIVE_STAGES = {"flowering", "fruiting", "maturity", "harvest_ready"}

# L3 spray check
SPRAY_WINDOW_START_HOUR = 6
SPRAY_WINDOW_END_HOUR = 18          # exclusive end: hours 06:00..17:00
SPRAY_RAIN_TOTAL_MM = 1.0
SPRAY_RAIN_PROB_PCT = 50
SPRAY_MAX_WIND_KMH = 15
SPRAY_HEAT_C = 35
SPRAY_BLOCK_HOURS = 3

# L5 risk score (IMD-style daily rainfall bands)
RISK_HEAVY_RAIN_MM = 64.5
RISK_MODERATE_RAIN_MM = 15.6
RISK_HEAT_C = 40
RISK_GUST_KMH = 40
RISK_POINTS = {"heavy_rain": 3, "moderate_rain": 1, "heat": 2, "gust": 1, "hail": 3}
RISK_SENSITIVE_MULTIPLIER = 1.5
RISK_LEVELS = [(0, 1, "low"), (2, 3, "medium"), (4, None, "high")]
RISK_FORECAST_DAYS = 5
# WMO weather codes for thunderstorm with hail
HAIL_WEATHER_CODES = {96, 99}

# L6 monitor
MONITOR_LOOKBACK_DAYS = 3
MONITOR_DEDUPE_DAYS = 2
POST_HARVEST_WINDOW_DAYS = 14

# L8 NDVI
NDVI_MAX_MASKED_PCT = 30
NDVI_WINDOW_DAYS = 20

# Misc limits
LOG_TEXT_MAX = 500
NOTES_MAX = 500
QUESTION_MAX = 300
PHOTO_MAX_BYTES = 8 * 1024 * 1024
DUPLICATE_WINDOW_MINUTES = 10
AGENT_MAX_TOOL_CALLS = 6
MANDI_STALE_DAYS = 7

# Claim-record fields shown in the evidence pack. The team must check these against the
# official PMFBY loss-intimation documents before a real pilot; the LLM never decides them.
CLAIM_FIELDS = [
    "Farmer name", "Village / District / State", "Survey (khasra) number", "Crop and season",
    "Area (acres)", "Insurance application / policy number (if any)", "Type of loss event",
    "Date of loss event", "Date loss was noticed / confirmed", "Estimated extent of loss",
]

# Mandi commodity names on Agmarknet / data.gov.in
MANDI_COMMODITY = {"paddy": "Paddy(Dhan)(Common)", "wheat": "Wheat", "tomato": "Tomato"}

# Fallback parser keyword maps (L1.5). Order matters: first match wins.
CATEGORY_KEYWORDS = [
    ("sale", ["becha", "bechi", "beche", "sold", "sale", "sell", "बेचा", "बेची"]),
    ("harvest", ["katai ki", "harvested", "harvest kiya", "upaj", "paidawar", "nikla", "निकला", "कटाई की"]),
    ("fertiliser", ["dap", "urea", "yuria", "khad", "khaad", "fertiliser", "fertilizer", "fym", "gobar",
                    "potash", "npk", "zinc", "खाद", "यूरिया", "डीएपी"]),
    ("pesticide", ["spray", "dawa", "dawai", "pesticide", "insecticide", "fungicide", "keetnashak",
                   "दवा", "छिड़काव"]),
    ("seed", ["beej", "seed", "seedling", "paudh", "nursery", "बीज", "पौध"]),
    ("irrigation", ["paani", "pani", "sinchai", "irrigation", "irrigate", "pump", "watered", "पानी", "सिंचाई"]),
    ("labour", ["majdoor", "mazdoor", "labour", "labor", "majduri", "worker", "katai", "harvesting",
                "ropai", "transplant", "मजदूर", "मजदूरी", "कटाई", "रोपाई"]),
    ("land_prep", ["jutai", "ploughing", "plough", "tractor", "rotavator", "land prep", "staking",
                   "जुताई", "ट्रैक्टर"]),
    ("sowing", ["sowed", "sown", "sowing", "buwai", "buai", "boya", "बुवाई", "बोया"]),
]
ITEM_KEYWORDS = ["dap", "urea", "fym", "potash", "npk", "zinc", "tractor", "diesel"]
UNIT_KEYWORDS = {
    "kg": ["kg", "kilo", "किलो"], "bag": ["bag", "bags", "bori", "बोरी", "बैग"],
    "quintal": ["quintal", "qtl", "q", "kuntal", "क्विंटल"], "litre": ["litre", "liter", "l", "ltr", "लीटर"],
    "hour": ["hour", "hours", "hr", "hrs", "ghanta", "ghante", "घंटा", "घंटे"],
    "day": ["day", "days", "din", "दिन"], "acre": ["acre", "acres", "bigha", "एकड़"],
}
