from __future__ import annotations

import json
from datetime import date
from hashlib import sha1
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


CEIDG_API_URLS = [
    "https://dane.biznes.gov.pl/api/ceidg/v3/firmy",
    "https://dane.biznes.gov.pl/api/ceidg/v2/firmy",
]

MF_VAT_API_URL = "https://wl-api.mf.gov.pl/api/search/nip/{nip}?date={date}"


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


def _request_json(url: str, headers: dict | None = None):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SaldoFlow/1.0",
            **(headers or {}),
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"HTTP {exc.code}: {body[:300]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Nie udało się połączyć z usługą: {exc}") from exc


def _first_company_record(payload, nip: str) -> dict:
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        candidates = []

        # CEIDG / różne możliwe struktury
        for key in ["data", "items", "results", "content", "firmy", "firma"]:
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, dict):
                candidates.append(value)

        # MF Biała Lista VAT
        result = payload.get("result")
        if isinstance(result, dict):
            subject = result.get("subject")
            subjects = result.get("subjects")

            if isinstance(subject, dict):
                candidates.append(subject)

            if isinstance(subjects, list):
                candidates.extend(subjects)

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

    raise RuntimeError("Nie znaleziono danych dla podanego NIP.")


def _compose_address(record: dict) -> str:
    direct = _pick(record, ["workingAddress", "residenceAddress", "adres"])
    if direct:
        return direct

    street = _pick(record, ["ulica", "nazwaUlicy"])
    building = _pick(record, ["budynek", "nrBudynku", "numerBudynku"])
    flat = _pick(record, ["lokal", "nrLokalu", "numerLokalu"])
    postal = _pick(record, ["kodPocztowy"])
    city = _pick(record, ["miejscowosc", "poczta", "miasto"])

    line1 = " ".join(part for part in [street, building] if part)
    if flat:
        line1 = f"{line1}/{flat}" if line1 else flat

    line2 = " ".join(part for part in [postal, city] if part)

    return ", ".join(part for part in [line1, line2] if part)


def _normalize_company(record: dict, nip: str, source: str) -> dict[str, str]:
    first_name = _pick(record, ["imie", "imiePierwsze", "pierwszeImie"])
    last_name = _pick(record, ["nazwisko"])
    owner = " ".join(part for part in [first_name, last_name] if part)

    name = _pick(
        record,
        [
            "name",
            "nazwa",
            "firma",
            "nazwaFirmy",
            "nazwaPrzedsiebiorcy",
            "nazwaPelna",
        ],
    )

    status = _pick(
        record,
        [
            "statusVat",
            "status",
            "statusDzialalnosci",
            "statusRejestru",
        ],
    )

    return {
        "nazwa": name or owner or f"Kontrahent {nip}",
        "nip": _clean_nip(_pick(record, ["nip", "NIP"]) or nip),
        "regon": _pick(record, ["regon", "REGON"]),
        "adres": _compose_address(record),
        "email": _pick(record, ["email", "adresPocztyElektronicznej", "adresEmail"]),
        "telefon": _pick(record, ["telefon", "numerTelefonu"]),
        "strona_www": _pick(record, ["www", "stronaWWW", "adresStronyInternetowej"]),
        "status_rejestru": status,
        "wlasciciel": owner,
        "source": source,
    }


def _lookup_via_mf_vat(nip: str) -> dict[str, str]:
    today = date.today().isoformat()
    url = MF_VAT_API_URL.format(nip=nip, date=today)
    payload = _request_json(url)
    record = _first_company_record(payload, nip)
    return _normalize_company(record, nip, "mf_vat")


def _lookup_via_ceidg(nip: str, token: str) -> dict[str, str]:
    urls = []

    custom_url = getattr(settings, "CEIDG_API_URL", "")
    if custom_url:
        urls.append(custom_url)

    urls.extend(CEIDG_API_URLS)

    seen = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]

    errors = []

    for base_url in urls:
        url = f"{base_url}?{urlencode({'nip': nip})}"

        for auth_header in [
            f"Bearer {token}",
            f"Bearer{token}",
            token,
        ]:
            try:
                payload = _request_json(
                    url,
                    headers={
                        "Authorization": auth_header,
                    },
                )
                record = _first_company_record(payload, nip)
                return _normalize_company(record, nip, "ceidg")
            except Exception as exc:
                errors.append(f"{url}: {exc}")

    raise RuntimeError("CEIDG nie odpowiedziało poprawnie. " + " | ".join(errors[-3:]))


def _demo_company_by_nip(nip: str) -> dict[str, str]:
    cities = [
        ("Białystok", "15-001"),
        ("Warszawa", "00-120"),
        ("Gdańsk", "80-101"),
        ("Kraków", "31-154"),
    ]
    streets = ["Słoneczna", "Przemysłowa", "Kwiatowa", "Lipowa"]
    first_names = ["Anna", "Michał", "Katarzyna", "Piotr"]
    last_names = ["Nowak", "Kowalski", "Mazur", "Wiśniewski"]

    digest = sha1(nip.encode("ascii")).digest()
    city, postal = cities[digest[0] % len(cities)]
    street = streets[digest[1] % len(streets)]
    first = first_names[digest[2] % len(first_names)]
    last = last_names[digest[3] % len(last_names)]

    return {
        "nazwa": f"Usługi {first} {last}",
        "nip": nip,
        "regon": f"{int.from_bytes(digest[4:8], 'big') % 10**9:09d}",
        "adres": f"ul. {street} {1 + digest[8] % 80}, {postal} {city}",
        "email": "",
        "telefon": "",
        "strona_www": "",
        "status_rejestru": "AKTYWNY (demo)",
        "wlasciciel": f"{first} {last}",
        "source": "demo",
    }


def lookup_company_by_nip(nip: str):
    nip = _clean_nip(nip)

    if len(nip) != 10:
        raise ValueError("Podaj poprawny NIP.")

    token = getattr(settings, "CEIDG_AUTH_TOKEN", "")

    # 1. Najpierw próbujemy CEIDG, jeśli token jest ustawiony.
    if token:
        try:
            return _lookup_via_ceidg(nip, token)
        except Exception:
            # 2. Jeśli CEIDG zwróci 404 albo inny błąd, bierzemy dane z oficjalnej Białej Listy VAT MF.
            return _lookup_via_mf_vat(nip)

    # 3. Bez tokenu też próbujemy MF, bo nie wymaga klucza.
    try:
        return _lookup_via_mf_vat(nip)
    except Exception:
        if getattr(settings, "CEIDG_DEMO_MODE", False):
            return _demo_company_by_nip(nip)
        raise RuntimeError("Nie udało się pobrać danych po NIP.")
