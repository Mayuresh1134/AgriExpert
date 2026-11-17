"""Central government schemes for farmers, and a simple eligibility check against the farm.

Facts were checked in November 2026 against official sources and press releases (PIB).
Amounts and rules change: every card links to the official portal, which has the last word.
State schemes are not listed; the state agriculture department portal has them.
"""
from __future__ import annotations

CHECKED = "November 2026"

SCHEMES = [
    {
        "id": "pm_kisan", "name": "PM-KISAN", "full": "Pradhan Mantri Kisan Samman Nidhi", "category": "income",
        "benefit": "₹6,000 a year, paid as three instalments of ₹2,000 straight into your bank account.",
        "who": "All landholding farmer families. Not for income-tax payers, government employees (except "
               "class IV), pensioners getting ₹10,000+ a month, or professionals such as doctors and lawyers.",
        "documents": ["Aadhaar", "Bank account linked to Aadhaar", "Land records in your name"],
        "how": "Register at pmkisan.gov.in, through a Common Service Centre (CSC) or the village patwari, and complete e-KYC.",
        "url": "https://pmkisan.gov.in", "rule": "landowner",
    },
    {
        "id": "pmfby", "name": "PMFBY crop insurance", "full": "Pradhan Mantri Fasal Bima Yojana", "category": "insurance",
        "benefit": "Pays out when the crop is lost to drought, flood, pests, hailstorm or other natural causes, "
                   "including losses after harvest from cyclones and unseasonal rain.",
        "who": "All farmers growing notified crops in notified areas, including tenants and sharecroppers. "
               "Your premium: 2% of the sum insured for kharif food and oilseed crops, 1.5% for rabi, 5% for "
               "commercial and horticultural crops. The government pays the rest.",
        "documents": ["Aadhaar", "Bank passbook", "Land record or tenancy agreement", "Sowing certificate"],
        "how": "Enrol through your bank, a CSC, the crop insurance app or pmfby.gov.in before the season's cut-off date.",
        "url": "https://pmfby.gov.in", "rule": "insurance",
    },
    {
        "id": "kcc", "name": "Kisan Credit Card", "full": "Kisan Credit Card with interest subvention", "category": "credit",
        "benefit": "Short-term crop loans at 7% interest, cut to an effective 4% if you repay on time. "
                   "Under the Modified Interest Subvention Scheme the loan limit is ₹5 lakh, and up to ₹2 lakh "
                   "needs no collateral.",
        "who": "Owner farmers, tenant farmers, sharecroppers and self-help groups; also for dairy, poultry and fisheries.",
        "documents": ["Aadhaar", "Land records", "Passport photo", "Bank's KCC form"],
        "how": "Apply at any bank branch, cooperative bank or regional rural bank; many accept applications at a CSC.",
        "url": "https://www.myscheme.gov.in/schemes/kcc", "rule": "all",
    },
    {
        "id": "shc", "name": "Soil Health Card", "full": "Soil Health Card scheme", "category": "advice",
        "benefit": "Free soil test of your field with a card giving the nutrient status and fertiliser doses for your crops. "
                   "Fertiliser advice in this app becomes field-specific once you enter the card's results.",
        "who": "All farmers.", "documents": ["Aadhaar", "Field survey number"],
        "how": "Contact the agriculture office or KVK; samples are collected by the department or taken to a soil testing lab.",
        "url": "https://soilhealth.dac.gov.in", "rule": "no_soil_test",
    },
    {
        "id": "pm_kmy", "name": "PM Kisan Maan-Dhan", "full": "Pradhan Mantri Kisan Maan-Dhan Yojana", "category": "pension",
        "benefit": "A pension of ₹3,000 a month from age 60. You pay ₹55-200 a month depending on your joining age; the "
                   "government adds the same amount.",
        "who": "Small and marginal farmers (up to 2 hectares, about 5 acres) aged 18-40.",
        "documents": ["Aadhaar", "Bank account", "Land records"],
        "how": "Enrol at a CSC or on maandhan.in. PM-KISAN beneficiaries can pay the contribution from their PM-KISAN money.",
        "url": "https://maandhan.in", "rule": "small_young",
    },
    {
        "id": "pmksy", "name": "Drip & sprinkler subsidy", "full": "PMKSY - Per Drop More Crop", "category": "irrigation",
        "benefit": "Subsidy on drip and sprinkler irrigation: 55% of the cost for small and marginal farmers and 45% for "
                   "others (many states add a top-up). Saves 30-50% water and often raises yields.",
        "who": "All farmers with a water source; priority to small and marginal farmers.",
        "documents": ["Aadhaar", "Land records", "Bank account", "Quotation from a registered company"],
        "how": "Apply through the state agriculture or horticulture department portal.",
        "url": "https://pmksy.gov.in", "rule": "irrigation",
    },
    {
        "id": "kusum", "name": "PM-KUSUM solar pumps", "full": "PM Kisan Urja Suraksha evam Utthaan Mahabhiyan",
        "category": "irrigation",
        "benefit": "Standalone solar pumps or solarised grid pumps with 30% central and 30% state subsidy; the farmer pays "
                   "about 40%, of which most can be a bank loan. Cuts diesel and electricity bills.",
        "who": "Individual farmers, groups, FPOs and cooperatives, especially in areas without a reliable grid supply.",
        "documents": ["Aadhaar", "Land records", "Bank account"],
        "how": "Apply on the state's renewable-energy agency or PM-KUSUM portal.",
        "url": "https://pmkusum.mnre.gov.in", "rule": "irrigation",
    },
    {
        "id": "smam", "name": "Farm machinery subsidy", "full": "Sub-Mission on Agricultural Mechanisation", "category": "machinery",
        "benefit": "40-50% subsidy on tractors, power tillers, seed drills, sprayers and other machines; up to 80% for "
                   "Custom Hiring Centres run by groups.",
        "who": "All farmers; higher rates for small, marginal, SC/ST and women farmers.",
        "documents": ["Aadhaar", "Land records", "Bank account", "Caste certificate if applicable"],
        "how": "Apply on the state agriculture department's DBT portal or agrimachinery.nic.in.",
        "url": "https://agrimachinery.nic.in", "rule": "all",
    },
    {
        "id": "enam", "name": "e-NAM online market", "full": "National Agriculture Market", "category": "market",
        "benefit": "Sell to buyers across the country through an online auction at your local e-NAM mandi; payment goes "
                   "straight to your bank account.",
        "who": "All farmers selling at one of the 1,400+ e-NAM mandis.",
        "documents": ["Aadhaar", "Bank account"], "how": "Register at enam.gov.in, the e-NAM app, or the mandi's e-NAM desk.",
        "url": "https://enam.gov.in", "rule": "all",
    },
    {
        "id": "pkvy", "name": "Organic farming support", "full": "Paramparagat Krishi Vikas Yojana", "category": "organic",
        "benefit": "₹31,500 per hectare over three years for groups of farmers converting to organic farming, including "
                   "certification and marketing help.",
        "who": "Farmers joining a cluster or group of about 20 hectares.",
        "documents": ["Aadhaar", "Land records"], "how": "Contact the district agriculture office.",
        "url": "https://pgsindia-ncof.gov.in", "rule": "all",
    },
    {
        "id": "aif", "name": "Agriculture Infrastructure Fund", "full": "Agriculture Infrastructure Fund", "category": "credit",
        "benefit": "Loans up to ₹2 crore with 3% interest subvention for warehouses, cold storage, sorting and grading units.",
        "who": "Farmers, FPOs, cooperatives, self-help groups and agri-entrepreneurs.",
        "documents": ["Project report", "Aadhaar", "Land documents"], "how": "Apply on agriinfra.dac.gov.in or through a bank.",
        "url": "https://agriinfra.dac.gov.in", "rule": "large",
    },
]


def check(farm: dict | None, user: dict | None) -> list[dict]:
    """Every scheme, with whether it looks relevant to this farm and why."""
    farm = farm or {}
    acres = float(farm.get("land_area_acres") or 0)
    ha = acres / 2.471
    age = (user or {}).get("age")
    out = []
    for s in SCHEMES:
        rule, match, why = s["rule"], "maybe", None
        if rule == "all":
            match = "yes"
        elif rule == "landowner":
            if farm.get("ownership") == "tenant":
                match, why = "no", "PM-KISAN needs land in your name; tenant farmers are not covered."
            elif farm.get("ownership") == "owned":
                match, why = "yes", "You own the land you farm."
        elif rule == "insurance":
            match = "yes"
            why = "Insure every season you grow a notified crop."
        elif rule == "no_soil_test":
            if farm.get("soil_status") and any(farm["soil_status"].values()):
                match, why = "done", "You have already entered soil test results."
            else:
                match, why = "yes", "No soil test entered yet."
        elif rule == "small_young":
            if acres and ha > 2:
                match, why = "no", f"For farms up to 2 ha (about 5 acres); yours is {acres:g} acres."
            elif age and not 18 <= age <= 40:
                match, why = "no", "Joining age is 18-40."
            elif acres and age:
                match, why = "yes", f"{acres:g} acres and age {age}."
            elif acres:
                match, why = "maybe", "Fits your land size; you also need to be 18-40 years old."
        elif rule == "irrigation":
            if farm.get("irrigation") == "none":
                match, why = "maybe", "Useful if you have or plan a well, borewell or pond."
            else:
                match, why = "yes", "You irrigate: drip or solar can cut water and energy costs."
        elif rule == "large":
            match = "maybe"
            why = "For storage and processing projects, alone or as a group."
        out.append({**{k: v for k, v in s.items() if k != "rule"}, "match": match, "why": why})
    order = {"yes": 0, "maybe": 1, "done": 2, "no": 3}
    out.sort(key=lambda s: order[s["match"]])
    return out
