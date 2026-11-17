"""Crop knowledge base: the agronomy and price facts every other module reads.

One entry per crop. Figures are general package-of-practice values for India (ICAR / state
agricultural university style recommendations); local advice from a Krishi Vigyan Kendra
or a Soil Health Card should take priority where it differs.

Units
  npk            kg of N, P2O5, K2O per hectare
  water_mm       seasonal water need, low to high
  days           days after sowing when each phase ends: emergence, vegetative, flowering, maturity
  seed_rate      per acre, as text
  depth_cm       sowing / planting depth range
  germ_temp      soil temperature range that suits germination, deg C
  temp           air temperature range the crop grows well in, deg C
  store_moisture safe grain moisture for storage, percent (None where it does not apply)

Prices
  msp   Minimum Support Price announced by the Government of India, Rs per quintal:
        kharif crops -> Kharif Marketing Season 2026-27 (CCEA, 13 May 2026)
        rabi crops   -> Rabi Marketing Season 2027-28 (CCEA, 30 Sep 2026)
        sugarcane    -> Fair and Remunerative Price, sugar season 2026-27 (CCEA, 5 May 2026)
  cost_qtl  CACP cost of production (A2+FL), Rs per quintal. For rabi crops and sugarcane it
        is the figure in the announcement; for kharif crops it is worked back from the MSP and
        the announced margin (50%, or 61/56/56/54% for moong/bajra/maize/tur).
  farmgate   share of the mandi price a grower typically gets selling at the farm (banana only)
  cost_acre  for crops with no CACP figure: a rough typical cost of cultivation per acre.
        These are hand-set estimates and vary a lot by region - treat them as placeholders.
"""

SEASONS = {
    "kharif": {"label": "Kharif (monsoon)", "sow_months": [6, 7], "months": [6, 7, 8, 9, 10]},
    "rabi": {"label": "Rabi (winter)", "sow_months": [10, 11], "months": [10, 11, 12, 1, 2, 3]},
    "summer": {"label": "Summer (zaid)", "sow_months": [2, 3], "months": [3, 4, 5, 6]},
}

SOIL_TYPES = {
    "alluvial": "Alluvial (river plains)",
    "black": "Black (regur / cotton soil)",
    "red": "Red",
    "laterite": "Laterite",
    "sandy": "Sandy / desert",
    "loamy": "Loamy",
    "clay": "Clay",
}

STAGES = [
    ("preparation", "Land preparation"),
    ("sowing", "Sowing"),
    ("germination", "Germination"),
    ("vegetative", "Vegetative growth"),
    ("flowering", "Flowering"),
    ("maturation", "Maturation"),
    ("harvesting", "Harvest & storage"),
]


def _c(name, local, category, seasons, days, *, apy=None, yield_factor=1.0, product=None, mandi=None,
       msp=None, msp_note=None, cost_qtl=None, cost_acre=None, npk=(0, 0, 0),
       water_mm=(0, 0), soils=(), ph=(6.0, 7.5), temp=(15, 35), germ_temp=(15, 35), seed_rate="",
       spacing="", depth_cm=None, critical_water=(), pests=(), harvest_sign="", storage="",
       store_moisture=None, stage_labels=None, notes="", sow_months=None, split_n=None, nursery_days=0,
       farmgate=1.0):
    return {
        "name": name, "local": local, "category": category, "seasons": list(seasons),
        "days": {"emergence": days[0], "vegetative": days[1], "flowering": days[2], "maturity": days[3]},
        "apy": apy or [], "yield_factor": yield_factor, "product": product or name.lower(),
        "mandi": mandi, "msp": msp, "msp_note": msp_note,
        "cost_qtl": cost_qtl, "cost_acre": cost_acre, "npk": list(npk), "water_mm": list(water_mm),
        "soils": list(soils), "ph": list(ph), "temp": list(temp), "germ_temp": list(germ_temp),
        "seed_rate": seed_rate, "spacing": spacing, "depth_cm": list(depth_cm) if depth_cm else None,
        "critical_water": list(critical_water), "pests": list(pests), "harvest_sign": harvest_sign,
        "storage": storage, "store_moisture": store_moisture, "stage_labels": stage_labels or {},
        "notes": notes, "sow_months": sow_months or {}, "split_n": split_n or [0.5, 0.25, 0.25],
        "nursery_days": nursery_days, "farmgate": farmgate,
    }


K27 = "Kharif Marketing Season 2026-27"
R28 = "Rabi Marketing Season 2027-28"

CROPS = {
    # ------------------------------------------------------------------ cereals
    "rice": _c(
        "Rice (paddy)", "धान", "cereal", ["kharif", "rabi", "summer"], (10, 65, 95, 130),
        apy=["Rice"], yield_factor=1.49, product="paddy", mandi="Paddy (Dhan)",
        msp=2441, msp_note=f"Common paddy, {K27}", cost_qtl=1627, npk=(120, 60, 40), water_mm=(1000, 1300),
        soils=["clay", "alluvial", "loamy", "black"], ph=(5.0, 7.5), temp=(20, 35), germ_temp=(20, 35),
        seed_rate="8-10 kg (transplanted), 25-30 kg (direct seeded)", spacing="20 x 15 cm",
        depth_cm=(2, 3), critical_water=["tillering", "panicle initiation", "flowering"],
        pests=["Blast", "Bacterial leaf blight", "Brown plant hopper", "Stem borer"],
        harvest_sign="80-85% of the grains in the panicle have turned straw-yellow and feel hard.",
        storage="Dry paddy to 14% moisture for sale and 12% for longer storage; store in clean, dry bags on pallets.",
        store_moisture=12, nursery_days=25, split_n=[0.5, 0.25, 0.25],
        notes="District statistics report milled rice; estimates here are converted to paddy (rice / 0.67).",
        sow_months={"kharif": [6, 7], "rabi": [11, 12], "summer": [1, 2]},
    ),
    "wheat": _c(
        "Wheat", "गेहूं", "cereal", ["rabi"], (8, 60, 90, 125),
        apy=["Wheat"], mandi="Wheat", msp=2610, msp_note=R28, cost_qtl=1264, npk=(120, 60, 40),
        water_mm=(450, 650), soils=["loamy", "alluvial", "clay", "black"], ph=(6.0, 7.5), temp=(10, 25),
        germ_temp=(16, 25), seed_rate="40 kg (timely sown), 50 kg (late sown)", spacing="rows 20-22.5 cm apart",
        depth_cm=(4, 5), critical_water=["crown root initiation (20-25 days)", "tillering", "flowering", "grain filling"],
        pests=["Yellow (stripe) rust", "Brown rust", "Karnal bunt", "Aphids", "Termites"],
        harvest_sign="Plants turn golden yellow and grains are hard; grain moisture about 20% for hand harvest, 14% for combine.",
        storage="Dry to 10-12% moisture; store in clean metal bins or bags, away from walls.", store_moisture=12,
        split_n=[0.5, 0.5, 0.0], sow_months={"rabi": [11, 12]},
        notes="Sow by mid-November where possible: every week of delay after late November costs yield.",
    ),
    "maize": _c(
        "Maize", "मक्का", "cereal", ["kharif", "rabi", "summer"], (7, 50, 65, 100),
        apy=["Maize"], mandi="Maize", msp=2410, msp_note=K27, cost_qtl=1545,
        npk=(120, 60, 40), water_mm=(500, 800), soils=["loamy", "alluvial", "red", "black"], ph=(5.8, 7.5),
        temp=(18, 32), germ_temp=(18, 32), seed_rate="8 kg (hybrids)", spacing="60 x 20 cm", depth_cm=(4, 5),
        critical_water=["knee-high stage", "tasselling", "silking", "grain filling"],
        pests=["Fall armyworm", "Stem borer", "Turcicum (northern) leaf blight", "Common rust"],
        harvest_sign="Husks turn dry and papery and a black layer forms at the base of the kernels.",
        storage="Dry cobs, shell, then dry grain to 12% moisture; maize spoils fast if stored damp (aflatoxin risk).",
        store_moisture=12, split_n=[0.34, 0.33, 0.33], sow_months={"kharif": [6, 7], "rabi": [10, 11], "summer": [2, 3]},
        notes="Maize cannot stand waterlogging: make sure the field drains within a day of heavy rain.",
    ),
    "jowar": _c(
        "Jowar (sorghum)", "ज्वार", "cereal", ["kharif", "rabi"], (7, 55, 75, 110),
        apy=["Jowar"], mandi="Jowar", msp=4023, msp_note=f"Hybrid, {K27}", cost_qtl=2682, npk=(80, 40, 40),
        water_mm=(400, 600), soils=["black", "loamy", "red", "alluvial"], ph=(6.0, 8.0), temp=(20, 35),
        germ_temp=(18, 35), seed_rate="3-4 kg", spacing="45 x 15 cm", depth_cm=(3, 4),
        critical_water=["booting", "flowering", "grain filling"],
        pests=["Shoot fly", "Stem borer", "Grain mould", "Downy mildew"],
        harvest_sign="Grains are hard and a black spot shows at the base of the grain.",
        storage="Dry to 12% moisture before bagging.", store_moisture=12, sow_months={"kharif": [6, 7], "rabi": [9, 10]},
    ),
    "bajra": _c(
        "Bajra (pearl millet)", "बाजरा", "cereal", ["kharif", "summer"], (5, 40, 55, 85),
        apy=["Bajra"], mandi="Bajra", msp=2900, msp_note=K27, cost_qtl=1859, npk=(60, 30, 30),
        water_mm=(300, 450), soils=["sandy", "loamy", "red", "black"], ph=(6.0, 8.0), temp=(22, 36),
        germ_temp=(20, 35), seed_rate="1.5-2 kg", spacing="45 x 12 cm", depth_cm=(2, 3),
        critical_water=["tillering", "flowering", "grain filling"],
        pests=["Downy mildew", "Ergot", "Blast", "Shoot fly"],
        harvest_sign="Ear heads turn brown and grains are hard when pressed.",
        storage="Dry to 12% moisture; bajra flour turns rancid quickly, so store as whole grain.", store_moisture=12,
        sow_months={"kharif": [6, 7], "summer": [2, 3]},
    ),
    "ragi": _c(
        "Ragi (finger millet)", "रागी / मडुआ", "cereal", ["kharif", "rabi"], (7, 55, 80, 115),
        apy=["Ragi"], mandi="Ragi", msp=5205, msp_note=K27, cost_qtl=3470, npk=(50, 40, 25),
        water_mm=(400, 550), soils=["red", "laterite", "loamy", "sandy"], ph=(5.0, 7.5), temp=(18, 32),
        germ_temp=(18, 32), seed_rate="2 kg (transplanted), 4 kg (direct sown)", spacing="22.5 x 10 cm",
        depth_cm=(2, 3), critical_water=["tillering", "flowering"],
        pests=["Blast (leaf, neck and finger)", "Stem borer", "Aphids"],
        harvest_sign="Ear heads turn brown; harvest in two pickings as ears mature unevenly.",
        storage="Dry to 12% moisture; ragi stores well for years when kept dry.", store_moisture=12,
        sow_months={"kharif": [6, 7], "rabi": [9, 10]},
    ),
    "barley": _c(
        "Barley", "जौ", "cereal", ["rabi"], (8, 60, 90, 125),
        apy=["Barley"], mandi="Barley (Jau)", msp=2286, msp_note=R28, cost_qtl=1447, npk=(60, 30, 20),
        water_mm=(300, 450), soils=["loamy", "sandy", "alluvial"], ph=(6.5, 8.0), temp=(10, 25), germ_temp=(14, 25),
        seed_rate="35-40 kg", spacing="rows 22.5 cm apart", depth_cm=(4, 5),
        critical_water=["tillering (30-35 days)", "flowering"],
        pests=["Yellow rust", "Covered smut", "Aphids"],
        harvest_sign="Crop turns golden and the ears bend; harvest promptly as ripe barley shatters.",
        storage="Dry to 12% moisture.", store_moisture=12, sow_months={"rabi": [10, 11]},
        notes="Tolerates saline and poorer soils better than wheat and needs only 2-3 irrigations.",
    ),
    # ------------------------------------------------------------------- pulses
    "gram": _c(
        "Gram (chickpea)", "चना", "pulse", ["rabi"], (10, 50, 80, 110),
        apy=["Gram"], mandi="Bengal Gram (Chana)", msp=5958, msp_note=R28, cost_qtl=3751,
        npk=(20, 40, 20), water_mm=(250, 400), soils=["loamy", "black", "alluvial"], ph=(6.0, 8.0), temp=(15, 30),
        germ_temp=(15, 28), seed_rate="30-32 kg (desi), 40 kg (kabuli)", spacing="30 x 10 cm", depth_cm=(6, 8),
        critical_water=["branching (pre-flowering)", "pod filling"],
        pests=["Pod borer (Helicoverpa)", "Fusarium wilt", "Ascochyta blight", "Dry root rot"],
        harvest_sign="Leaves turn reddish-brown and drop; pods are straw-coloured and rattle.",
        storage="Dry to 9-10% moisture; pulses are attacked by bruchid beetles, so use airtight or hermetic bags.",
        store_moisture=10, split_n=[1.0, 0, 0], sow_months={"rabi": [10, 11]},
        notes="Do not irrigate at flowering: it causes flower drop. Treat seed with Rhizobium culture.",
    ),
    "tur": _c(
        "Tur / arhar (pigeon pea)", "अरहर / तूर", "pulse", ["kharif"], (8, 90, 130, 165),
        apy=["Arhar/Tur"], mandi="Red Gram (Tur)", msp=8450, msp_note=K27, cost_qtl=5487,
        npk=(25, 50, 25), water_mm=(500, 700), soils=["loamy", "black", "red", "alluvial"], ph=(6.0, 7.5),
        temp=(18, 35), germ_temp=(20, 35), seed_rate="5-6 kg", spacing="90 x 20 cm", depth_cm=(4, 5),
        critical_water=["flower initiation", "pod filling"],
        pests=["Pod borer", "Pod fly", "Fusarium wilt", "Sterility mosaic"],
        harvest_sign="About 80% of the pods have turned brown and dry.",
        storage="Dry to 9-10% moisture; store whole grain in airtight containers against bruchids.", store_moisture=10,
        split_n=[1.0, 0, 0], sow_months={"kharif": [6, 7]},
        notes="Often grown as an intercrop with soybean, cotton or jowar. Very sensitive to waterlogging.",
    ),
    "moong": _c(
        "Moong (green gram)", "मूंग", "pulse", ["kharif", "summer", "rabi"], (5, 30, 45, 65),
        apy=["Moong(Green Gram)"], mandi="Green Gram (Moong)", msp=8780, msp_note=K27,
        cost_qtl=5453, npk=(20, 40, 20), water_mm=(250, 400), soils=["loamy", "sandy", "alluvial", "red", "black"],
        ph=(6.2, 7.5), temp=(25, 35), germ_temp=(20, 35), seed_rate="6-8 kg (kharif), 10-12 kg (summer)",
        spacing="30 x 10 cm", depth_cm=(3, 4), critical_water=["flowering", "pod filling"],
        pests=["Yellow mosaic virus (whitefly)", "Cercospora leaf spot", "Powdery mildew", "Pod borer"],
        harvest_sign="Pods turn black or brown; pick in 2-3 rounds because pods shatter when left.",
        storage="Dry to 9-10% moisture; store airtight.", store_moisture=10, split_n=[1.0, 0, 0],
        sow_months={"kharif": [6, 7], "summer": [3, 4], "rabi": [10, 11]},
        notes="A short crop that fits between wheat harvest and kharif sowing where irrigation is available.",
    ),
    "urad": _c(
        "Urad (black gram)", "उड़द", "pulse", ["kharif", "rabi", "summer"], (6, 35, 55, 80),
        apy=["Urad"], mandi="Black Gram (Urad)", msp=8200, msp_note=K27, cost_qtl=5467,
        npk=(20, 40, 20), water_mm=(250, 400), soils=["loamy", "black", "clay", "alluvial"], ph=(6.0, 7.8),
        temp=(25, 35), germ_temp=(20, 35), seed_rate="6-8 kg", spacing="30 x 10 cm", depth_cm=(3, 4),
        critical_water=["flowering", "pod filling"],
        pests=["Yellow mosaic virus (whitefly)", "Powdery mildew", "Leaf crinkle", "Pod borer"],
        harvest_sign="Most pods have turned black and dry.",
        storage="Dry to 9-10% moisture; store airtight.", store_moisture=10, split_n=[1.0, 0, 0],
        sow_months={"kharif": [6, 7], "rabi": [10, 11], "summer": [2, 3]},
    ),
    "masoor": _c(
        "Masoor (lentil)", "मसूर", "pulse", ["rabi"], (10, 55, 85, 120),
        apy=["Masoor"], mandi="Lentil (Masur, whole)", msp=7390, msp_note=R28, cost_qtl=3854,
        npk=(20, 40, 20), water_mm=(250, 400), soils=["loamy", "alluvial", "clay", "black"], ph=(6.0, 8.0),
        temp=(15, 28), germ_temp=(15, 25), seed_rate="14-16 kg", spacing="25 x 5 cm", depth_cm=(3, 4),
        critical_water=["pre-flowering", "pod filling"], pests=["Rust", "Wilt", "Aphids", "Pod borer"],
        harvest_sign="Plants turn yellow-brown and lower pods rattle; harvest in the morning to cut shattering.",
        storage="Dry to 9-10% moisture; store airtight.", store_moisture=10, split_n=[1.0, 0, 0],
        sow_months={"rabi": [10, 11]},
    ),
    # ----------------------------------------------------------------- oilseeds
    "groundnut": _c(
        "Groundnut", "मूंगफली", "oilseed", ["kharif", "rabi", "summer"], (8, 30, 75, 115),
        apy=["Groundnut"], mandi="Groundnut", msp=7517, msp_note=f"In shell, {K27}", cost_qtl=5011,
        npk=(25, 50, 45), water_mm=(500, 700), soils=["sandy", "loamy", "red", "black"], ph=(6.0, 7.5),
        temp=(22, 33), germ_temp=(20, 32), seed_rate="40-50 kg of kernels", spacing="30 x 10 cm", depth_cm=(4, 5),
        critical_water=["flowering", "pegging", "pod development"],
        pests=["Tikka (leaf spot)", "Rust", "Collar rot", "Leaf miner", "White grub"],
        harvest_sign="Leaves yellow and the inside of the pod shell turns dark; kernels are plump with coloured skin.",
        storage="Dry pods to 8-9% moisture in the shade; damp groundnut develops aflatoxin.", store_moisture=9,
        split_n=[1.0, 0, 0], sow_months={"kharif": [6, 7], "rabi": [11, 12], "summer": [1, 2]},
        stage_labels={"flowering": "Flowering, pegging & pod formation"},
        notes="Apply gypsum (about 200 kg per acre) near the plants at flowering/pegging for well-filled pods.",
    ),
    "soybean": _c(
        "Soybean", "सोयाबीन", "oilseed", ["kharif"], (6, 40, 65, 100),
        apy=["Soyabean"], mandi="Soyabean", msp=5708, msp_note=f"Yellow, {K27}", cost_qtl=3805,
        npk=(30, 60, 40), water_mm=(450, 700), soils=["black", "loamy", "alluvial"], ph=(6.0, 7.5), temp=(20, 32),
        germ_temp=(20, 32), seed_rate="25-30 kg", spacing="45 x 5 cm", depth_cm=(3, 4),
        critical_water=["flowering", "pod filling"],
        pests=["Girdle beetle", "Stem fly", "Yellow mosaic virus", "Rust", "Tobacco caterpillar"],
        harvest_sign="Leaves turn yellow and fall; pods are brown and seeds rattle. Do not delay: pods shatter.",
        storage="Dry to 10-11% moisture; soybean seed loses germination fast if stored damp or piled high.",
        store_moisture=10, split_n=[1.0, 0, 0], sow_months={"kharif": [6, 7]},
        notes="Sow only after 75-100 mm of monsoon rain has fallen. Treat seed with Rhizobium and PSB.",
    ),
    "mustard": _c(
        "Rapeseed & mustard", "सरसों", "oilseed", ["rabi"], (6, 40, 75, 125),
        apy=["Rapeseed &Mustard"], mandi="Mustard", msp=6613, msp_note=R28, cost_qtl=3367,
        npk=(80, 40, 40), water_mm=(250, 400), soils=["loamy", "alluvial", "sandy", "clay"], ph=(6.0, 7.8),
        temp=(10, 25), germ_temp=(15, 25), seed_rate="1.5-2 kg", spacing="30-45 x 10-15 cm", depth_cm=(2, 3),
        critical_water=["rosette / pre-flowering (30-35 days)", "pod filling (60-70 days)"],
        pests=["Mustard aphid", "White rust", "Alternaria blight", "Painted bug", "Sawfly"],
        harvest_sign="75% of the pods turn golden yellow; harvest in the early morning to avoid shattering.",
        storage="Dry to 8% moisture before storage.", store_moisture=8, split_n=[0.5, 0.5, 0],
        sow_months={"rabi": [10]},
        notes="Mustard responds strongly to sulphur: apply about 16 kg S per acre (for example through SSP or gypsum).",
    ),
    "sunflower": _c(
        "Sunflower", "सूरजमुखी", "oilseed", ["kharif", "rabi", "summer"], (7, 50, 70, 95),
        apy=["Sunflower"], mandi="Sunflower seed", msp=8343, msp_note=K27, cost_qtl=5562, npk=(60, 60, 40),
        water_mm=(500, 750), soils=["loamy", "black", "alluvial", "red"], ph=(6.5, 8.0), temp=(20, 30),
        germ_temp=(15, 30), seed_rate="2-2.5 kg (hybrids)", spacing="60 x 30 cm", depth_cm=(3, 5),
        critical_water=["bud initiation", "flowering", "seed filling"],
        pests=["Head borer (Helicoverpa)", "Alternaria leaf spot", "Necrosis disease", "Birds at maturity"],
        harvest_sign="The back of the head turns lemon yellow and the bracts brown.",
        storage="Dry seed to 9% moisture.", store_moisture=9, sow_months={"kharif": [6, 7], "rabi": [10, 11], "summer": [1, 2]},
        notes="Keeping bee hives nearby, or hand pollination with a soft cloth at flowering, improves seed set.",
    ),
    "sesame": _c(
        "Sesame (til)", "तिल", "oilseed", ["kharif", "summer", "rabi"], (5, 35, 60, 88),
        apy=["Sesamum"], mandi="Sesame (Til)", msp=10346, msp_note=K27, cost_qtl=6897, npk=(40, 20, 20),
        water_mm=(300, 500), soils=["sandy", "loamy", "red", "alluvial", "black"], ph=(5.5, 8.0), temp=(25, 35),
        germ_temp=(22, 35), seed_rate="1.5-2 kg (mix with sand for even sowing)", spacing="30 x 10 cm",
        depth_cm=(2, 3), critical_water=["flowering", "capsule formation"],
        pests=["Phyllody", "Leaf webber / capsule borer", "Phytophthora blight", "Gall fly"],
        harvest_sign="Leaves yellow and drop, lower capsules turn yellow. Cut before capsules split open.",
        storage="Stack bundles upright to dry, thresh, then dry seed to 6-8% moisture.", store_moisture=7,
        sow_months={"kharif": [6, 7], "summer": [2, 3], "rabi": [10, 11]},
    ),
    "safflower": _c(
        "Safflower", "कुसुम / करडी", "oilseed", ["rabi"], (8, 65, 100, 135),
        apy=["Safflower"], mandi="Safflower", msp=7215, msp_note=R28, cost_qtl=4810, npk=(40, 40, 20),
        water_mm=(250, 400), soils=["black", "loamy", "alluvial"], ph=(6.0, 8.0), temp=(15, 30), germ_temp=(15, 25),
        seed_rate="4-5 kg", spacing="45 x 20 cm", depth_cm=(4, 5), critical_water=["rosette to branching", "flowering"],
        pests=["Aphids", "Alternaria leaf spot", "Wilt", "Capsule borer"],
        harvest_sign="Leaves and most bracts turn brown; harvest in the early morning when spines are soft.",
        storage="Dry seed to 8% moisture.", store_moisture=8, sow_months={"rabi": [9, 10]},
        notes="A deep-rooted crop that does well on stored moisture in black soils with little irrigation.",
    ),
    "castor": _c(
        "Castor", "अरंडी", "oilseed", ["kharif"], (10, 50, 110, 180),
        apy=["Castor Seed"], mandi="Castor seed", cost_acre=17000, npk=(60, 40, 20), water_mm=(500, 700),
        soils=["sandy", "red", "loamy", "black", "alluvial"], ph=(5.5, 8.0), temp=(20, 35), germ_temp=(20, 35),
        seed_rate="2-3 kg (hybrids)", spacing="90 x 60 cm", depth_cm=(5, 6),
        critical_water=["primary spike formation", "secondary spike development"],
        pests=["Semilooper", "Capsule borer", "Botrytis grey mould", "Wilt"],
        harvest_sign="Capsules on a spike turn yellow-brown; pick spikes in 3-4 rounds as they mature.",
        storage="Sun-dry spikes, thresh, and store seed at 8-9% moisture.", store_moisture=9,
        sow_months={"kharif": [6, 7, 8]}, stage_labels={"flowering": "Spike formation", "maturation": "Capsule maturity & pickings"},
    ),
    # ---------------------------------------------------------- fibre and cash crops
    "cotton": _c(
        "Cotton", "कपास", "fibre", ["kharif"], (7, 55, 110, 170),
        apy=["Cotton(Lint)"], yield_factor=0.5, product="seed cotton (kapas)", mandi="Cotton",
        msp=8267, msp_note=f"Medium staple, {K27}", cost_qtl=5511, npk=(100, 50, 50), water_mm=(700, 1200),
        soils=["black", "alluvial", "loamy", "red"], ph=(6.0, 8.0), temp=(21, 35), germ_temp=(18, 35),
        seed_rate="2 packets of Bt hybrid seed (about 0.9 kg)", spacing="90 x 60 cm (varies with hybrid)",
        depth_cm=(3, 5), critical_water=["squaring", "flowering", "boll development"],
        pests=["Pink bollworm", "Whitefly", "Jassids", "Thrips", "Leaf curl virus", "Boll rot"],
        harvest_sign="Bolls burst open fully; pick clean, dry kapas in the morning after dew has dried, every 15-20 days.",
        storage="Keep kapas dry (below 10-12% moisture), off the ground, and separate by picking and grade.",
        store_moisture=10, split_n=[0.34, 0.33, 0.33], sow_months={"kharif": [5, 6, 7]},
        stage_labels={"flowering": "Flowering & boll formation", "maturation": "Boll opening & pickings"},
        notes="District statistics report lint in 170 kg bales; estimates here are converted to seed cotton (lint is about 34%).",
    ),
    "sugarcane": _c(
        "Sugarcane", "गन्ना", "cash", ["annual"], (35, 240, 270, 330),
        apy=["Sugarcane"], product="cane", msp=365, msp_note="Fair and Remunerative Price at 10.25% recovery, sugar season 2026-27",
        cost_qtl=182, npk=(250, 115, 115), water_mm=(1500, 2500), soils=["loamy", "alluvial", "black", "clay"],
        ph=(6.0, 7.7), temp=(20, 35), germ_temp=(20, 35), seed_rate="12,000-14,000 two-budded setts",
        spacing="rows 90-120 cm apart", depth_cm=(5, 7),
        critical_water=["germination", "tillering (formative phase)", "grand growth"],
        pests=["Early shoot borer", "Top borer", "Red rot", "Smut", "Woolly aphid", "White grub"],
        harvest_sign="Cane is 10-12 months old, lower leaves dry, and juice brix is 18% or more.",
        storage="Do not store: deliver cane to the mill within 24 hours of cutting or it loses sugar.",
        split_n=[0.34, 0.33, 0.33], sow_months={"annual": [1, 2, 3, 10, 11]},
        stage_labels={"germination": "Germination of setts", "vegetative": "Tillering & grand growth",
                      "flowering": "Ripening begins", "maturation": "Ripening"},
        notes="Prices here use the central FRP; several states announce a higher State Advised Price.",
    ),
    "jute": _c(
        "Jute", "जूट / पाट", "fibre", ["kharif"], (7, 90, 110, 120),
        apy=["Jute"], yield_factor=0.18, product="raw jute fibre", mandi="Jute", cost_acre=30000,
        npk=(60, 30, 30), water_mm=(500, 800), soils=["alluvial", "loamy", "clay"], ph=(5.5, 7.5), temp=(24, 37),
        germ_temp=(22, 35), seed_rate="2-2.5 kg (line sowing)", spacing="25 x 5-7 cm", depth_cm=(2, 3),
        critical_water=["early growth before monsoon sets in"],
        pests=["Stem rot", "Semilooper", "Yellow mite", "Bihar hairy caterpillar"],
        harvest_sign="Harvest at the small-pod stage (110-120 days) for the best mix of yield and fibre quality.",
        storage="Ret bundles in slow clean water for 10-20 days, strip, wash, and sun-dry the fibre fully before baling.",
        sow_months={"kharif": [3, 4, 5]}, stage_labels={"flowering": "Flowering / small pods", "maturation": "Harvest & retting"},
        notes="District statistics report jute in 180 kg bales; estimates here are in tonnes of fibre.",
    ),
    # --------------------------------------------------------- vegetables and spices
    "onion": _c(
        "Onion", "प्याज", "vegetable", ["kharif", "rabi"], (10, 90, 120, 140),
        apy=["Onion"], mandi="Onion", cost_acre=60000, npk=(100, 50, 50), water_mm=(350, 550),
        soils=["loamy", "alluvial", "sandy", "red"], ph=(6.0, 7.5), temp=(13, 30), germ_temp=(15, 28),
        seed_rate="3-4 kg of seed for the nursery", spacing="15 x 10 cm", depth_cm=(1, 2),
        critical_water=["establishment after transplanting", "bulb initiation", "bulb development"],
        pests=["Thrips", "Purple blotch", "Stemphylium blight", "Basal rot"],
        harvest_sign="50-75% of the tops have fallen over. Stop irrigating 10-15 days before harvest.",
        storage="Cure in the field for 3-5 days and in shade for 10-15 days; store in a well-ventilated structure (chawl).",
        nursery_days=45, split_n=[0.34, 0.33, 0.33], sow_months={"kharif": [5, 6], "rabi": [10, 11]},
        stage_labels={"flowering": "Bulb development", "maturation": "Bulb maturity"},
        notes="Rabi onion stores for months; kharif onion keeps poorly and is usually sold soon after harvest.",
    ),
    "potato": _c(
        "Potato", "आलू", "vegetable", ["rabi"], (15, 40, 75, 100),
        apy=["Potato"], mandi="Potato", cost_acre=65000, npk=(150, 80, 100), water_mm=(500, 700),
        soils=["sandy", "loamy", "alluvial"], ph=(5.2, 7.0), temp=(15, 25), germ_temp=(15, 22),
        seed_rate="8-10 quintals of seed tubers", spacing="60 x 20 cm", depth_cm=(5, 7),
        critical_water=["stolon formation", "tuber initiation", "tuber bulking"],
        pests=["Late blight", "Early blight", "Aphids (virus carriers)", "Cutworm", "Tuber moth"],
        harvest_sign="Haulms yellow and dry. Cut the haulms 10-15 days before digging so the skin sets.",
        storage="Cure in shade for 10-15 days; hold in cold storage at 2-4 C (10-12 C for chipping varieties).",
        split_n=[0.5, 0.5, 0], sow_months={"rabi": [10, 11]},
        stage_labels={"germination": "Sprout emergence", "flowering": "Tuber bulking", "maturation": "Tuber maturity"},
        notes="Tubers form best when nights are cool (below about 20 C). Earth up at 25-30 days.",
    ),
    "tomato": _c(
        "Tomato", "टमाटर", "vegetable", ["kharif", "rabi", "summer"], (8, 55, 85, 125),
        mandi="Tomato", cost_acre=75000, npk=(120, 80, 80), water_mm=(600, 800),
        soils=["loamy", "sandy", "red", "black", "alluvial"], ph=(6.0, 7.0), temp=(18, 30), germ_temp=(18, 30),
        seed_rate="60-80 g of hybrid seed for the nursery", spacing="60 x 45 cm", depth_cm=(1, 1),
        critical_water=["transplant establishment", "flowering", "fruit development"],
        pests=["Early blight", "Late blight", "Leaf curl virus (whitefly)", "Fruit borer", "Bacterial wilt"],
        harvest_sign="Pick at breaker (turning) stage for distant markets, fully red for local sale.",
        storage="Does not store long: 1-2 weeks at 12-15 C. Grade and pack in ventilated crates.",
        nursery_days=25, split_n=[0.34, 0.33, 0.33], sow_months={"kharif": [6, 7], "rabi": [10, 11], "summer": [1, 2]},
        stage_labels={"flowering": "Flowering & fruit set", "maturation": "Fruit development & pickings"},
        notes="No district production records are available for tomato, so it is not ranked in recommendations.",
    ),
    "chilli": _c(
        "Chilli (dry)", "मिर्च", "spice", ["kharif", "rabi"], (10, 70, 110, 165),
        apy=["Dry Chillies"], product="dry chilli", mandi="Mirchi (Dry Red Chilli)", cost_acre=80000,
        npk=(100, 50, 50), water_mm=(600, 900), soils=["loamy", "black", "red", "alluvial"], ph=(6.0, 7.5),
        temp=(20, 32), germ_temp=(20, 30), seed_rate="80-100 g hybrid seed (400 g for open-pollinated varieties)",
        spacing="60 x 45 cm", depth_cm=(1, 1), critical_water=["flowering", "fruit development"],
        pests=["Thrips", "Mites", "Leaf curl", "Anthracnose (fruit rot / die-back)", "Fruit borer"],
        harvest_sign="For dry chilli, pick fully red ripe fruits; 5-6 pickings over two months.",
        storage="Dry on clean tarpaulin to 8-10% moisture; never dry on bare soil (aflatoxin, colour loss).",
        store_moisture=10, nursery_days=40, split_n=[0.34, 0.33, 0.33], sow_months={"kharif": [5, 6], "rabi": [9, 10]},
        stage_labels={"flowering": "Flowering & fruit set", "maturation": "Ripening & pickings"},
    ),
    "turmeric": _c(
        "Turmeric", "हल्दी", "spice", ["annual", "kharif"], (30, 150, 210, 240),
        apy=["Turmeric"], product="cured dry turmeric", mandi="Turmeric", cost_acre=90000, npk=(120, 60, 120),
        water_mm=(1200, 1500), soils=["loamy", "alluvial", "red", "laterite"], ph=(5.0, 7.5), temp=(20, 35),
        germ_temp=(25, 35), seed_rate="8-10 quintals of seed rhizomes", spacing="45 x 25 cm", depth_cm=(5, 7),
        critical_water=["sprouting", "rhizome initiation", "rhizome development"],
        pests=["Rhizome rot", "Leaf blotch", "Leaf spot", "Shoot borer", "Rhizome scale"],
        harvest_sign="Leaves turn yellow and dry (7-9 months). Cut the tops, then dig carefully.",
        storage="Boil, sun-dry for 10-15 days to 8-10% moisture, and polish. Keep seed rhizomes in pits under shade.",
        store_moisture=10, split_n=[0.34, 0.33, 0.33], sow_months={"annual": [5, 6], "kharif": [5, 6]},
        stage_labels={"germination": "Sprouting", "flowering": "Rhizome development", "maturation": "Rhizome maturity"},
    ),
    "garlic": _c(
        "Garlic", "लहसुन", "spice", ["rabi"], (10, 80, 120, 145),
        apy=["Garlic"], mandi="Garlic", cost_acre=65000, npk=(100, 50, 50), water_mm=(400, 600),
        soils=["loamy", "alluvial", "sandy"], ph=(6.0, 7.5), temp=(12, 28), germ_temp=(12, 24),
        seed_rate="2-2.5 quintals of cloves", spacing="15 x 10 cm", depth_cm=(3, 5),
        critical_water=["establishment", "bulb formation"],
        pests=["Thrips", "Purple blotch", "Stemphylium blight", "Mites"],
        harvest_sign="Tops turn yellow-brown and start to bend over. Stop irrigating 10-15 days earlier.",
        storage="Cure in shade for a week with tops on; hang in bunches or store in ventilated crates.",
        split_n=[0.34, 0.33, 0.33], sow_months={"rabi": [10, 11]},
        stage_labels={"flowering": "Bulb formation", "maturation": "Bulb maturity"},
    ),
    "coriander": _c(
        "Coriander (seed)", "धनिया", "spice", ["rabi"], (12, 45, 75, 100),
        apy=["Coriander"], mandi="Coriander seed", cost_acre=18000, npk=(60, 30, 20), water_mm=(300, 450),
        soils=["loamy", "black", "alluvial"], ph=(6.0, 8.0), temp=(15, 28), germ_temp=(15, 25),
        seed_rate="5-6 kg (split the seed into halves before sowing)", spacing="30 x 10 cm", depth_cm=(2, 3),
        critical_water=["flowering", "seed formation"],
        pests=["Powdery mildew", "Stem gall", "Wilt", "Aphids"],
        harvest_sign="Seeds on the main umbels change from green to brown; cut early in the morning.",
        storage="Dry in shade to keep colour and aroma, to 9-10% moisture; store in lined bags.", store_moisture=10,
        split_n=[0.5, 0.5, 0], sow_months={"rabi": [10, 11]},
        notes="Frost at flowering can wipe out the crop; a light irrigation before a frosty night helps.",
    ),
    "banana": _c(
        "Banana", "केला", "fruit", ["annual"], (30, 210, 270, 360),
        apy=["Banana"], mandi="Banana", cost_acre=180000, farmgate=0.5, npk=(600, 180, 900),
        water_mm=(1800, 2200), soils=["loamy", "alluvial", "black", "red"], ph=(6.0, 7.5), temp=(15, 35),
        germ_temp=(20, 35), seed_rate="1,200-1,400 suckers or tissue-culture plants", spacing="1.8 x 1.8 m",
        depth_cm=None, critical_water=["establishment", "shooting (bunch emergence)", "bunch development"],
        pests=["Panama (Fusarium) wilt", "Sigatoka leaf spot", "Bunchy top virus", "Rhizome weevil", "Nematodes"],
        harvest_sign="Fingers lose their ridges and look full and round, 90-120 days after the bunch emerges.",
        storage="Hold green bunches at 13-14 C; ripen in a ripening chamber, never with calcium carbide.",
        split_n=[0.25, 0.5, 0.25], sow_months={"annual": [6, 7, 2, 3]},
        stage_labels={"sowing": "Planting", "germination": "Establishment", "flowering": "Shooting (bunch emergence)",
                      "maturation": "Bunch development"},
        notes="Mandi banana prices are mostly for ripened fruit at city markets; growers selling green bunches at the "
              "farm typically get about half, which is what the profit estimate assumes. Plant in 45 cm pits. Fertiliser is given per plant, roughly 200 g N, 60 g P2O5 and 300 g K2O in splits.",
    ),
}


def crop_ids() -> list[str]:
    return list(CROPS)


def get(crop_id: str) -> dict | None:
    crop = CROPS.get(crop_id)
    return {"id": crop_id, **crop} if crop else None


def public_summary(crop_id: str) -> dict:
    c = CROPS[crop_id]
    return {"id": crop_id, "name": c["name"], "local": c["local"], "category": c["category"],
            "seasons": c["seasons"], "duration_days": c["days"]["maturity"], "msp": c["msp"]}
