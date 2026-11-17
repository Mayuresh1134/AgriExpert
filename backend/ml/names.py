"""Name clean-up shared by the data preparation scripts.

Government datasets spell districts differently from each other and from today's maps
(Gurgaon/Gurugram, Allahabad/Prayagraj ...). These tables line them up.
"""
import difflib
import re

# Older state a district was reported under -> state it belongs to today.
SUCCESSOR_STATES = {
    "Bihar": ["Jharkhand"],
    "Madhya Pradesh": ["Chhattisgarh"],
    "Uttar Pradesh": ["Uttarakhand"],
    "Andhra Pradesh": ["Telangana"],
    "Jammu and Kashmir": ["Ladakh"],
    "Jammu & Kashmir": ["Ladakh"],
}

STATE_ALIASES = {
    "andamanandnicobarisland": "Andaman and Nicobar Islands",
    "andamanandnicobar": "Andaman and Nicobar Islands",
    "andamannicobar": "Andaman and Nicobar Islands",
    "dadraandnagarhaveli": "Dadra and Nagar Haveli and Daman and Diu",
    "thedadraandnagarhaveli": "Dadra and Nagar Haveli and Daman and Diu",
    "damananddiu": "Dadra and Nagar Haveli and Daman and Diu",
    "dadranagarhaveli": "Dadra and Nagar Haveli and Daman and Diu",
    "jammukashmir": "Jammu and Kashmir",
    "orissa": "Odisha",
    "uttaranchal": "Uttarakhand",
    "uttrakhand": "Uttarakhand",
    "pondicherry": "Puducherry",
    "nctofdelhi": "Delhi",
    "chattisgarh": "Chhattisgarh",
    "tamilnadu": "Tamil Nadu",
    "westbengal": "West Bengal",
    "telengana": "Telangana",
    "himachal": "Himachal Pradesh",
    "chatisgarh": "Chhattisgarh",
    "dadarnagarhaveli": "Dadra and Nagar Haveli and Daman and Diu",
    "damananddui": "Dadra and Nagar Haveli and Daman and Diu",
}

# normalised old/variant district name -> name used on the map
DISTRICT_ALIASES = {
    "southandamans": "South Andaman", "nicobars": "Nicobars",
    "anantapur": "Anantapuramu", "kadapa": "YSR", "cuddapah": "YSR", "spsrnellore": "Sri Potti Sriramulu Nellore",
    "nellore": "Sri Potti Sriramulu Nellore", "visakhapatanam": "Visakhapatnam", "chittor": "Chittoor",
    "dibangvalley": "Upper Dibang Valley",
    "kamrupmetro": "Kamrup Metropolitan", "marigaon": "Morigaon", "southsalmaramancachar": "South Salmara Mankachar",
    "kaimurbhabua": "Kaimur", "pashchimchamparan": "West Champaran", "purbichamparan": "East Champaran",
    "bemetara": "Bametara", "dantewada": "Dakshin Bastar Dantewada", "gariyaband": "Gariaband",
    "kabirdham": "Kabeerdham", "kanker": "Uttar Bastar Kanker", "korea": "Koriya",
    "ahmadabad": "Ahmedabad", "chhotaudepur": "Chhota Udaipur", "dohad": "Dahod", "kachchh": "Kutch",
    "mahesana": "Mehsana", "panchmahals": "Panchmahal", "banaskantha": "Banaskantha", "sabarkantha": "Sabarkantha",
    "charkidadri": "Charkhi Dadri", "gurgaon": "Gurugram", "mewat": "Nuh",
    "lahulandspiti": "Lahaul and Spiti",
    "badgam": "Budgam", "poonch": "Punch", "rajauri": "Rajouri", "shopian": "Shopiyan",
    "lehladakh": "Leh", "ladakhleh": "Leh", "kargil": "Kargil", "nmandaman": "North and Middle Andaman",
    "eastsinghbum": "East Singhbhum", "sahebganj": "Sahibganj",
    "bagalkot": "Bagalkote", "bangalorerural": "Bengaluru Rural", "bangalore": "Bengaluru Urban",
    "bangaloreurban": "Bengaluru Urban", "belgaum": "Belagavi", "bellary": "Ballari", "bijapur": "Vijayapura",
    "chamarajanagar": "Chamarajanagara", "chikballapur": "Chikkaballapura", "chikmagalur": "Chikkamagaluru",
    "dakshinkannad": "Dakshina Kannada", "davangere": "Davanagere", "gulbarga": "Kalaburagi", "mysore": "Mysuru",
    "shimoga": "Shivamogga", "tumkur": "Tumakuru", "uttarkannad": "Uttara Kannada", "yadagiri": "Yadgir",
    "anugul": "Angul", "baleshwar": "Balasore", "jagatsinghapur": "Jagatsinghpur", "jajapur": "Jajpur",
    "nabarangpur": "Nabarangapur", "sonepur": "Subarnapur",
    "pondicherry": "Puducherry",
    "firozepur": "Ferozepur", "muktsar": "Sri Muktsar Sahib", "nawanshahr": "Shahid Bhagat Singh Nagar",
    "snagar": "Sahibzada Ajit Singh Nagar", "sasnagar": "Sahibzada Ajit Singh Nagar",
    "eastdistrict": "East Sikkim", "northdistrict": "North Sikkim", "southdistrict": "South Sikkim",
    "westdistrict": "West Sikkim",
    "kanchipuram": "Kancheepuram", "kanniyakumari": "Kanyakumari", "thenilgiris": "Nilgiris",
    "tuticorin": "Thoothukkudi", "villupuram": "Viluppuram",
    "mahbubnagar": "Mahabubnagar", "rangareddi": "Ranga Reddy", "warangal": "Warangal Urban",
    "bhadradri": "Bhadradri Kothagudem", "hanumakonda": "Warangal Urban", "jagitial": "Jagtial",
    "jangoan": "Jangaon", "jayashankar": "Jayashankar Bhupalapally", "jogulamba": "Jogulamba Gadwal",
    "komarambheemasifabad": "Komaram Bheem", "narayanapet": "Narayanpet", "rajanna": "Rajanna Sircilla",
    "yadadri": "Yadadri Bhuvanagiri",
    "sepahijala": "Sipahijala", "unakoti": "Unokoti",
    "allahabad": "Prayagraj", "faizabad": "Ayodhya", "kheri": "Lakhimpur Kheri",
    "santkabeernagar": "Sant Kabir Nagar", "santravidasnagar": "Bhadohi", "shravasti": "Shrawasti",
    "udamsinghnagar": "Udham Singh Nagar", "uttarkashi": "Uttarkashi", "rudraprayag": "Rudraprayag",
    "paraganasnorth": "North 24 Parganas", "paraganassouth": "South 24 Parganas",
    "24paraganasnorth": "North 24 Parganas", "24paraganassouth": "South 24 Parganas",
    "north24parganas": "North 24 Parganas", "south24parganas": "South 24 Parganas",
    "bardhaman": "Purba Bardhaman", "burdwan": "Purba Bardhaman",
    "dinajpurdakshin": "Dakshin Dinajpur", "dinajpuruttar": "Uttar Dinajpur", "maldah": "Malda",
    "medinipureast": "Purba Medinipur", "medinipurwest": "Paschim Medinipur", "medinipurw": "Paschim Medinipur",
    "medinipure": "Purba Medinipur", "hooghly": "Hooghly", "howrah": "Howrah",
    "mumbaisuburban": "Mumbai", "delhitotal": "New Delhi", "delhi": "New Delhi",
    "gaurellapendramarwahi": "Gaurela Pendra Marwahi",
    # spellings used in the IMD rainfall table
    "northcachar": "Dima Hasao", "jaintiahills": "West Jaintia Hills", "wkhasihill": "West Khasi Hills",
    "kephrie": "Kiphire", "southdinajpur": "Dakshin Dinajpur", "northdinajpur": "Uttar Dinajpur",
    "eastmidnapor": "Purba Medinipur", "westmidnapor": "Paschim Medinipur", "kandhamalphu": "Kandhamal",
    "keondjhargarh": "Kendujhar", "nawapara": "Nuapada", "khurda": "Khordha", "boudhgarh": "Boudh",
    "seraikelakha": "Seraikela Kharsawan", "purnea": "Purnia", "bhabua": "Kaimur",
    "sahujimahara": "Amethi", "ladakh": "Leh", "sonepat": "Sonipat", "seraikelakha": "Saraikela Kharsawan", "badaun": "Budaun", "mahamayanaga": "Hathras", "jyotibaphule": "Amroha",
    "gautambuddha": "Gautam Buddha Nagar", "kanshiramnag": "Kasganj", "garhwalpauri": "Pauri Garhwal",
    "garhwaltehri": "Tehri Garhwal", "shopan": "Shopiyan", "sriganganaga": "Ganganagar", "baroda": "Vadodara",
    "dnh": "Dadra and Nagar Haveli", "mumbaicity": "Mumbai", "mumbaisub": "Mumbai", "kowardha": "Kabeerdham",
    "kuddapah": "YSR", "belgam": "Belagavi", "bangalorerur": "Bengaluru Rural", "bangaloreurb": "Bengaluru Urban",
    "ramnagar": "Ramanagara", "chickballapur": "Chikkaballapura", "cannur": "Kannur",
    "thiruvanantha": "Thiruvananthapuram", "kherilakhimp": "Lakhimpur Kheri", "santravidas": "Bhadohi",
    "shravastingr": "Shrawasti", "udhamsinghn": "Udham Singh Nagar", "north24parg": "North 24 Parganas",
    "south24parg": "South 24 Parganas", "lahulspiti": "Lahaul and Spiti", "kamrupmetrop": "Kamrup Metropolitan",
    "lowerdibang": "Lower Dibang Valley", "chhimtuipui": "Lawngtlai", "sasnagar": "Sahibzada Ajit Singh Nagar",
}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


class DistrictMatcher:
    """Maps a (state, district) pair from any source to a (state, district) on our map."""

    def __init__(self, geo_districts):  # iterable of (state, district)
        self.by_state = {}
        for st, dt in geo_districts:
            self.by_state.setdefault(st, {})[norm(dt)] = dt
        self.state_names = {norm(s): s for s in self.by_state}
        self.cache = {}

    def state(self, name: str):
        n = norm(name)
        if n in self.state_names:
            return self.state_names[n]
        if n in STATE_ALIASES:
            return STATE_ALIASES[n]
        hit = difflib.get_close_matches(n, list(self.state_names), 1, 0.8)
        return self.state_names[hit[0]] if hit else None

    def _in_state(self, st, dn, fuzzy):
        table = self.by_state.get(st, {})
        if dn in table:
            return table[dn]
        alias = DISTRICT_ALIASES.get(dn)
        if alias and norm(alias) in table:
            return table[norm(alias)]
        if fuzzy:
            hit = difflib.get_close_matches(dn, list(table), 1, 0.86)
            if hit:
                return table[hit[0]]
        return None

    def match(self, state: str, district: str):
        key = (state, district)
        if key in self.cache:
            return self.cache[key]
        st = self.state(state)
        dn = norm(re.sub(r"\(.*$", "", str(district)))  # "Sonepat(Rtk)" -> "sonepat"
        result = None
        if st:
            candidates = [st] + SUCCESSOR_STATES.get(st, [])
            for fuzzy in (False, True):
                for cand in candidates:
                    hit = self._in_state(cand, dn, fuzzy)
                    if hit:
                        result = (cand, hit)
                        break
                if result:
                    break
        self.cache[key] = result
        return result
