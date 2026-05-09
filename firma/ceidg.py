from __future__ import annotations

import json
from hashlib import sha1
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


API_URL = getattr(
    settings,
    "CEIDG_API_URL",
    "https://dane.biznes.gov.pl/api/ceidg/v3/firmy",
)


DEMO_CITY_POOL = [
    ("Białystok", "15-001"),
    ("Warszawa", "00-120"),
    ("Gdańsk", "80-101"),
    ("Kraków", "31-154"),
    ("Lublin", "20-002"),
    ("Poznań", "61-725"),
]
DEMO_STREET_POOL = [
    "Słoneczna",
    "Przemysłowa",
    "Kwiatowa",
    "Lipowa",
    "Fabryczna",
    "Rzemieślnicza",
]
DEMO_FIRST_NAMES = ["Anna", "Michał", "Katarzyna", "Piotr", "Monika", "Tomasz"]
DEMO_LAST_NAMES = ["Nowak", "Kowalski", "Mazur", "Domański", "Jankowska", "Wiśniewski"]
DEMO_BUSINESS_WORDS = ["Studio", "Pracownia", "Biuro", "Usługi", "Technologie", "Serwis"]
DEMO_BUSINESS_SUFFIXES = ["Orbit", "Nova", "Amber", "Verto", "Nexa", "Forma"]


def _clean_nip(nip: str) -> str:
    return "".join(ch for ch in str(nip or "") if ch.isdigit())


def _norm_key(key: str) -> str:
    return str(key or "").lower().replace("_", "").replace("-", "").replace(" ", "")


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def _pick(record: dict, names: list[str]) -> str:
    wanted = {_norm_key(name) for name in names}

    for d in _walk_dicts(record):
        for key, value in d.items():
            if _norm_key(key) in wanted and value not in (None, ""):
                if isinstance(value, (dict, list)):
                    continue
                return str(value).strip()

    return ""


def _first_company_record(payload, nip: str) -> dict:
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = []

        for key in ["data", "items", "results", "content", "firmy", "firma"]:
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, dict):
                candidates.append(value)

        if not candidates:
            candidates = [payload]
    else:
        candidates = []

    for item in candidates:
        if not isinstance(item, dict):
            continue

        found_nip = _pick(item, ["nip", "NIP"])
        if not found_nip or _clean_nip(found_nip) == nip:
            return item

    for item in candidates:
        if isinstance(item, dict):
            return item

    raise RuntimeError("CEIDG nie zwróciło danych dla podanego NIP.")


def _compose_address(record: dict) -> str:
    address_candidates = []

    for d in _walk_dicts(record):
        for key, value in d.items():
            key_norm = _norm_key(key)
            if key_norm in {
                "adres",
                "adresdzialalnosci",
                "adresglownegomiejscawykonywaniadzialalnosci",
                "adresdodreczen",
                "adreskorespondencyjny",
            }:
                if isinstance(value, str):
                    return value.strip()
                if isinstance(value, dict):
                    address_candidates.append(value)

    if not address_candidates:
        address_candidates = [record]

    for address in address_candidates:
        street = _pick(address, ["ulica", "nazwaUlicy"])
        building = _pick(address, ["budynek", "nrBudynku", "numerBudynku"])
        flat = _pick(address, ["lokal", "nrLokalu", "numerLokalu"])
        postal = _pick(address, ["kodPocztowy"])
        city = _pick(address, ["miejscowosc", "poczta", "miasto"])

        line1 = " ".join(part for part in [street, building] if part)
        if flat:
            line1 = f"{line1}/{flat}" if line1 else flat

        line2 = " ".join(part for part in [postal, city] if part)

        result = ", ".join(part for part in [line1, line2] if part)
        if result:
            return result

    return ""


def _demo_company_by_nip(nip: str) -> dict[str, str]:
    digest = sha1(nip.encode("ascii")).digest()
    city, postal = DEMO_CITY_POOL[digest[0] % len(DEMO_CITY_POOL)]
    street = DEMO_STREET_POOL[digest[1] % len(DEMO_STREET_POOL)]
    building = 1 + digest[2] % 89
    first = DEMO_FIRST_NAMES[digest[3] % len(DEMO_FIRST_NAMES)]
    last = DEMO_LAST_NAMES[digest[4] % len(DEMO_LAST_NAMES)]
    business = DEMO_BUSINESS_WORDS[digest[5] % len(DEMO_BUSINESS_WORDS)]
    suffix = DEMO_BUSINESS_SUFFIXES[digest[6] % len(DEMO_BUSINESS_SUFFIXES)]

    company_name = f"{business} {suffix} {first} {last}"
    regon = f"{int.from_bytes(digest[7:11], 'big') % 10**9:09d}"
    phone = f"+48 {500 + digest[11] % 400} {100 + digest[12] % 900} {100 + digest[13] % 900}"
    email_local = f"{suffix.lower()}.{last.lower()}".replace("ł", "l")

    return {
        "nazwa": company_name,
        "nip": nip,
        "regon": regon,
        "adres": f"ul. {street} {building}, {postal} {city}",
        "email": f"kontakt@{email_local}.pl",
        "telefon": phone,
        "strona_www": f"https://www.{email_local}.pl",
        "status_rejestru": "AKTYWNY (tryb demonstracyjny)",
        "wlasciciel": f"{first} {last}",
        "source": "demo",
    }


def _request_api_json(nip: str, token: str):
    url = f"{API_URL}?{urlencode({'nip': nip})}"

    auth_variants = [
        f"Bearer {token}",
        token,
    ]

    last_error = None

    for auth_header in auth_variants:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": auth_header,
                "User-Agent": "SaldoFlow/1.0",
            },
        )

        try:
            with urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except HTTPError as exc:
            last_error = exc
            if exc.code in (401, 403):
                continue

            try:
                body = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""

            raise RuntimeError(f"Błąd CEIDG: HTTP {exc.code}. {body[:300]}") from exc
        except URLError as exc:
            raise RuntimeError("Nie udało się połączyć z CEIDG.") from exc

    if last_error is not None:
        raise RuntimeError(
            "CEIDG odrzuciło token. Sprawdź, czy klucz API jest aktywny "
            "i czy wkleiłeś go w Railway jako CEIDG_AUTH_TOKEN."
        )

    raise RuntimeError("Nie udało się pobrać danych z CEIDG.")


def _lookup_via_api(nip: str, token: str) -> dict[str, str]:
    payload = _request_api_json(nip, token)
    record = _first_company_record(payload, nip)

    first_name = _pick(record, ["imie", "imiePierwsze", "pierwszeImie"])
    last_name = _pick(record, ["nazwisko"])
    owner = " ".join(part for part in [first_name, last_name] if part)

    name = _pick(
        record,
        [
            "nazwa",
            "firma",
            "nazwaFirmy",
            "nazwaPrzedsiebiorcy",
            "nazwaPelna",
        ],
    )

    return {
        "nazwa": name or owner,
        "nip": _clean_nip(_pick(record, ["nip", "NIP"]) or nip),
        "regon": _pick(record, ["regon", "REGON"]),
        "adres": _compose_address(record),
        "email": _pick(record, ["email", "adresPocztyElektronicznej", "adresEmail"]),
        "telefon": _pick(record, ["telefon", "numerTelefonu"]),
        "strona_www": _pick(record, ["www", "stronaWWW", "adresStronyInternetowej"]),
        "status_rejestru": _pick(record, ["status", "statusDzialalnosci", "statusRejestru"]),
        "wlasciciel": owner,
        "source": "ceidg",
    }


def lookup_company_by_nip(nip: str):
    nip = _clean_nip(nip)

    if len(nip) != 10:
        raise ValueError("Podaj poprawny NIP.")

    token = getattr(settings, "CEIDG_AUTH_TOKEN", "")

    if token:
        return _lookup_via_api(nip, token)

    if getattr(settings, "CEIDG_DEMO_MODE", False):
        return _demo_company_by_nip(nip)

    raise RuntimeError("Pobieranie danych po NIP jest chwilowo niedostępne.")
