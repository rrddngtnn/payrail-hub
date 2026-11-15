"""Locale-aware autofill identity for payment checkout forms.

Generates plausible per-country billing profiles (name, address, phone) for
payment rails that require them (UPI, iDEAL, Pix, GoPay, MoMo, ...).
Profiles are deterministic per (country, seed) so a job can be resumed with
the same identity, and randomized per job when no seed is given.

No external service is contacted: everything is generated locally from
bundled name/geo tables. Override any field via environment variables
(e.g. UPI_BILLING_NAME) — explicit env config always wins.
"""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class BillingIdentity:
    name: str
    line1: str
    city: str
    state: str
    postal: str
    country: str  # ISO 3166-1 alpha-2
    phone: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


# First/last name pools per locale. Keep pools modest but plausible.
_NAMES = {
    "IN": {
        "first": ["Aarav", "Vivaan", "Aditya", "Ishaan", "Kabir", "Rohan", "Arjun", "Raj", "Vikram", "Ananya", "Priya", "Sneha", "Kavya"],
        "last": ["Sharma", "Patel", "Kumar", "Singh", "Gupta", "Mehta", "Iyer", "Nair", "Reddy", "Joshi"],
    },
    "ID": {
        "first": ["Budi", "Agus", "Dewi", "Siti", "Rizky", "Putra", "Andi", "Fitri", "Rina", "Joko"],
        "last": ["Santoso", "Wijaya", "Kusuma", "Hartono", "Pratama", "Saputra", "Hidayat", "Nugroho"],
    },
    "NL": {
        "first": ["Daan", "Sanne", "Lars", "Emma", "Joris", "Anouk", "Bram", "Fleur", "Niels", "Marieke"],
        "last": ["de Vries", "Jansen", "Bakker", "Visser", "Smit", "Mulder", "Bos", "Vos", "Peters"],
    },
    "BR": {
        "first": ["João", "Lucas", "Mateus", "Beatriz", "Carla", "Felipe", "Gabriel", "Marina", "Paulo"],
        "last": ["Silva", "Santos", "Oliveira", "Souza", "Costa", "Pereira", "Almeida", "Ferreira"],
    },
    "VN": {
        "first": ["Nam", "Linh", "Hieu", "Mai", "Tuan", "Hanh", "Long", "Thao", "Quang"],
        "last": ["Nguyen", "Tran", "Le", "Pham", "Hoang", "Vu", "Dang", "Bui"],
    },
    "PH": {
        "first": ["Jose", "Maria", "Juan", "Andrea", "Miguel", "Angel", "Katrina", "Paulo"],
        "last": ["Santos", "Reyes", "Cruz", "Bautista", "Ocampo", "Garcia", "Mendoza", "Villanueva"],
    },
    "TH": {
        "first": ["Somchai", "Niran", "Anong", "Malee", "Kanya", "Pranee", "Wichai", "Sri"],
        "last": ["Saetang", "Wong", "Chai", "Srisuk", "Kitti", "Thong", "Phan"],
    },
}

# Street/city/state/postal pools per locale. Postal formats match each
# country's real scheme so tax/zip validation passes when present.
_GEO = {
    "IN": {
        "streets": ["MG Road", "Park Street", "Brigade Road", "Anna Salai", "Linking Road", "Ring Road"],
        "cities": [("Mumbai", "MH", "400001"), ("Bengaluru", "KA", "560001"), ("New Delhi", "DL", "110001"), ("Chennai", "TN", "600001"), ("Kolkata", "WB", "700001"), ("Pune", "MH", "411001")],
        "phone_fmt": "+91-98%08d",
    },
    "ID": {
        "streets": ["Jalan Sudirman", "Jalan Gatot Subroto", "Jalan Kebon Sirih", "Jalan Asia Afrika", "Jalan Diponegoro"],
        "cities": [("Jakarta", "DKI", "10110"), ("Bandung", "JB", "40111"), ("Surabaya", "JI", "60119"), ("Yogyakarta", "YO", "55111")],
        "phone_fmt": "+62-8%09d",
    },
    "NL": {
        "streets": ["Keizersgracht", "Herengracht", "Kalverstraat", "Damstraat", "Prinsengracht", "Nieuwstraat"],
        "cities": [("Amsterdam", "NH", "1012"), ("Rotterdam", "ZH", "3011"), ("Utrecht", "UT", "3511"), ("Den Haag", "ZH", "2511")],
        "phone_fmt": "+31-6%08d",
    },
    "BR": {
        "streets": ["Rua Augusta", "Avenida Paulista", "Rua Oscar Freire", "Avenida Brasil", "Rua da Quitanda"],
        "cities": [("São Paulo", "SP", "01310"), ("Rio de Janeiro", "RJ", "20040"), ("Belo Horizonte", "MG", "30140"), ("Curitiba", "PR", "80010")],
        "phone_fmt": "+55-11-9%08d",
    },
    "VN": {
        "streets": ["Nguyen Hue", "Le Loi", "Tran Hung Dao", "Pham Ngu Lao", "Hai Ba Trung"],
        "cities": [("Ho Chi Minh City", "SG", "700000"), ("Hanoi", "HN", "100000"), ("Da Nang", "DN", "500000")],
        "phone_fmt": "+84-9%09d",
    },
    "PH": {
        "streets": ["Ayala Avenue", "Roxas Boulevard", "Taft Avenue", "Quezon Avenue", "Ortigas Avenue"],
        "cities": [("Manila", "MN", "1000"), ("Cebu City", "CB", "6000"), ("Davao City", "DA", "8000")],
        "phone_fmt": "+63-9%09d",
    },
    "TH": {
        "streets": ["Sukhumvit Road", "Silom Road", "Rama IV Road", "Ploenchit Road", "Wireless Road"],
        "cities": [("Bangkok", "BK", "10110"), ("Chiang Mai", "CM", "50000"), ("Phuket", "PK", "83000")],
        "phone_fmt": "+66-8%09d",
    },
}


def supported_countries() -> list[str]:
    return sorted(_GEO.keys())


def generate_billing_identity(country: str, seed: str | None = None) -> BillingIdentity:
    """Generate a plausible billing identity for a country.

    Deterministic when seed is provided; random otherwise.
    """
    cc = (country or "").upper()
    if cc not in _GEO:
        raise ValueError(f"unsupported country: {country!r} (supported: {', '.join(supported_countries())})")

    rng = random.Random(f"billing:{cc}:{seed}") if seed else random.Random()

    names = _NAMES.get(cc) or _NAMES["IN"]
    geo = _GEO[cc]
    first = rng.choice(names["first"])
    last = rng.choice(names["last"])
    # NL surname convention: "de Vries" capitalizes as-is
    name = f"{first} {last}"
    street_no = rng.randint(1, 999)
    line1 = f"{street_no} {rng.choice(geo['streets'])}"
    city, state, postal = rng.choice(geo["cities"])
    phone = geo["phone_fmt"] % rng.randint(10_000_000, 99_999_999)

    return BillingIdentity(
        name=name, line1=line1, city=city, state=state,
        postal=postal, country=cc, phone=phone,
    )


def env_billing_identity(country: str, env_prefix: str) -> BillingIdentity:
    """Build identity from env vars with autofill fallback.

    Precedence: explicit env vars (e.g. UPI_BILLING_NAME) > autofill.
    """
    cc = (country or "IN").upper()
    autofill = generate_billing_identity(cc)

    def _env(suffix: str, fallback: str) -> str:
        val = os.environ.get(f"{env_prefix}{suffix}", "").strip()
        return val or fallback

    return BillingIdentity(
        name=_env("NAME", autofill.name),
        line1=_env("LINE1", autofill.line1),
        city=_env("CITY", autofill.city),
        state=_env("STATE", autofill.state),
        postal=_env("POSTAL", autofill.postal),
        country=cc,
        phone=_env("PHONE", autofill.phone),
    )
