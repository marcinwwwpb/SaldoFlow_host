from __future__ import annotations

from hashlib import sha1
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from django.conf import settings

SOAP_URL = getattr(settings, "CEIDG_SOAP_URL", "https://datastore.ceidg.gov.pl/CEIDG.DataStore/Services/NewDataStoreProvider.svc")
SOAP_ACTION = "http://tempuri.org/INewDataStoreProvider/GetMigrationDataExtendedAddressInfo"

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


def _build_envelope(nip: str, token: str) -> bytes:
    envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/" xmlns:arr="http://schemas.microsoft.com/2003/10/Serialization/Arrays">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:GetMigrationDataExtendedAddressInfo>
      <tem:AuthToken>{token}</tem:AuthToken>
      <tem:NIP>
        <arr:string>{nip}</arr:string>
      </tem:NIP>
    </tem:GetMigrationDataExtendedAddressInfo>
  </soapenv:Body>
</soapenv:Envelope>'''
    return envelope.encode("utf-8")


def _find_text_anywhere(root, tag_names):
    for node in root.iter():
        local_name = node.tag.split("}")[-1]
        if local_name in tag_names and node.text:
            text = node.text.strip()
            if text:
                return text
    return ""


def _compose_address(root):
    address_root = None
    for node in root.iter():
        local_name = node.tag.split("}")[-1]
        if local_name in {"AdresGlownegoMiejscaWykonywaniaDzialalnosci", "AdresDoDoreczen"}:
            address_root = node
            break
    if address_root is None:
        return ""
    parts = [
        _find_text_anywhere(address_root, {"Ulica"}),
        _find_text_anywhere(address_root, {"Budynek"}),
        _find_text_anywhere(address_root, {"Lokal"}),
        _find_text_anywhere(address_root, {"KodPocztowy"}),
        _find_text_anywhere(address_root, {"Miejscowosc", "Poczta"}),
    ]
    return ", ".join(part for part in parts if part)


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


def _lookup_via_soap(nip: str, token: str) -> dict[str, str]:
    request = Request(
        SOAP_URL,
        data=_build_envelope(nip, token),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": SOAP_ACTION,
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"Błąd CEIDG: HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError("Nie udało się połączyć z CEIDG.") from exc

    root = ET.fromstring(payload)
    firma = _find_text_anywhere(root, {"Firma", "Nazwa"})
    if not firma:
        raise RuntimeError("CEIDG nie zwróciło danych dla podanego NIP.")

    owner_parts = [
        _find_text_anywhere(root, {"Imie"}),
        _find_text_anywhere(root, {"Nazwisko"}),
    ]
    wlasciciel = " ".join(part for part in owner_parts if part)

    return {
        "nazwa": firma,
        "nip": _find_text_anywhere(root, {"NIP"}) or nip,
        "regon": _find_text_anywhere(root, {"REGON"}),
        "adres": _compose_address(root),
        "email": _find_text_anywhere(root, {"AdresPocztyElektronicznej"}),
        "telefon": _find_text_anywhere(root, {"Telefon"}),
        "strona_www": _find_text_anywhere(root, {"AdresStronyInternetowej"}),
        "status_rejestru": _find_text_anywhere(root, {"Status"}),
        "wlasciciel": wlasciciel,
        "source": "ceidg",
    }


def lookup_company_by_nip(nip: str):
    nip = _clean_nip(nip)
    if len(nip) != 10:
        raise ValueError("Podaj poprawny NIP.")

    token = getattr(settings, "CEIDG_AUTH_TOKEN", "")
    if token:
        return _lookup_via_soap(nip, token)
    if getattr(settings, "CEIDG_DEMO_MODE", False):
        return _demo_company_by_nip(nip)
    raise RuntimeError("Pobieranie danych po NIP jest chwilowo niedostępne.")
