from dataclasses import dataclass, field
import re
import os
from typing import List, Optional, Union, IO

import pymarc
from pymarc import Field, Record

from marc_to_readable.utils import reverse_name


@dataclass
class ReadableRecord:
    ester_id: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    part_number: Optional[str] = None
    edition: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    publisher: Optional[str] = None
    year_published: Optional[str] = None
    city_published: Optional[str] = None
    num_pages: Optional[int] = None
    isbn: Optional[str] = None
    series: Optional[str] = None    
    series_number: Optional[str] = None
    dimensions: Optional[str] = None
    language: Optional[str] = None
    original_language: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    editors: List[str] = field(default_factory=list)  # toimetajad
    publishers: List[str] = field(default_factory=list)  # väljaandjad
    compilers: List[str] = field(default_factory=list)  # koostajad
    illustrators: List[str] = field(default_factory=list)  # illustreerijad
    translators: List[str] = field(default_factory=list)  # tõlkijad
    designers: List[str] = field(default_factory=list)  # kujundajad
    photographers: List[str] = field(default_factory=list)  # fotograafid


def get_stripped_subfield(field: Field, subfield_code: str) -> Optional[str]:
    value = field.get(subfield_code)
    if value:
        return value.strip().strip(";:,./").strip()
    return None


NUMBER_REGEX = re.compile(r"\d+", re.IGNORECASE)
BETWEEN_SQUARE_BRACKETS_REGEX = re.compile(r"\[(.*?)\]|(.*)", re.IGNORECASE)
YEAR_REGEX = re.compile(r"\d{4}")


def marcxml_to_readable(
    src: Union[str, os.PathLike, IO[bytes]], skip_digital: bool = False,
) -> List[ReadableRecord]:
    # Parse MARCXML records
    records: List[Record] = pymarc.marcxml.parse_xml_to_array(src)
    results = []

    for record in records:
        if skip_digital:
            fixed_field_value = record.get("008").value
            if fixed_field_value[23] == "q" or fixed_field_value[23] == "s":
                continue

        result = ReadableRecord(ester_id=record.get("001").value())

        # Extract Title (Field 245 - subfields a, b, and n)
        title_field = record.get("245")
        if title_field:
            result.title = get_stripped_subfield(title_field, "a")
            result.subtitle = get_stripped_subfield(title_field, "b")
            if "b14256381" in result.ester_id:
                print(f"The subtitle is {result.subtitle}")
            part_number = get_stripped_subfield(title_field, "n")
            if part_number:
                part_number_match = re.match(NUMBER_REGEX, part_number)
                result.part_number = (
                    part_number_match.group() if part_number_match else part_number
                )

        edition_field = record.get("250")
        if edition_field:
            result.edition = get_stripped_subfield(edition_field, "a")

        # Extract Authors (Fields 100 and 700 - subfield a)
        author = get_stripped_subfield(record.get("100", {}), "a")
        if author:
            author = reverse_name(author)
            result.authors.append(author)

        pub_field = record.get("260")
        if pub_field:
            # Extract Publisher (Field 260 - subfield b)
            result.publisher = get_stripped_subfield(pub_field, "b")

            # Extract Year Published (Field 260 - subfield c)
            year_published_subfield = get_stripped_subfield(pub_field, "c")
            if year_published_subfield:
                year_published = re.search(YEAR_REGEX, year_published_subfield)
                result.year_published = year_published.group() if year_published else None

            # Extract City Published (Field 260 - subfield a)
            city_published_subfield = get_stripped_subfield(pub_field, "a")

            if city_published_subfield:
                city_published = re.search(
                    BETWEEN_SQUARE_BRACKETS_REGEX, city_published_subfield
                )
                if city_published.group(1):
                    result.city_published = city_published.group(1)
                else:
                    result.city_published = city_published.group(2)

        # Extract ISBN (Field 020 - subfield a)
        isbn_field = record.get("020")

        if isbn_field:
            isbn_type = isbn_field.get("q")
            if isbn_type:
                if "pdf" not in isbn_type.lower():
                    result.isbn = get_stripped_subfield(isbn_field, "a")
            else:
                result.isbn = get_stripped_subfield(isbn_field, "a")

        # Extract Series Information (Field 490 - subfields a, v)
        series_field = record.get("490")
        if series_field:
            result.series = get_stripped_subfield(series_field, "a")
            result.series_number = get_stripped_subfield(series_field, "v")

        physical_description_field = record.get("300")
        if physical_description_field:
            # Extract Number of Pages (Field 300 - subfield a)
            num_pages_subfield = get_stripped_subfield(physical_description_field, "a")
            if num_pages_subfield:
                num_pages = re.match(NUMBER_REGEX, num_pages_subfield)
                result.num_pages = num_pages.group() if num_pages else None

            # Extract Dimensions (Field 300 - subfield c)
            result.dimensions = get_stripped_subfield(physical_description_field, "c")

        lang_field = record.get("008")
        if lang_field:
            # Extract Language (Field 008 - character positions 35-37)
            result.language = lang_field.value()[35:38]

        # Extract Original Language (Field 041 - subfield h)
        original_language_field = record.get("041")
        if original_language_field:
            result.original_language = get_stripped_subfield(
                original_language_field, "h"
            )

        # Extract Genres (Field 655 - subfield a)
        for field in record.get_fields("655"):
            genre = get_stripped_subfield(field, "a")
            if genre:
                result.genres.append(genre)

        # Extract specific roles (Field 700)
        for field in record.get_fields("700"):
            role = get_stripped_subfield(field, "e") or get_stripped_subfield(
                field, "4"
            )
            name = get_stripped_subfield(field, "a")
            if role and name:
                name = reverse_name(name)
                role = role.lower()
                if "autor" == role and name not in result.authors:
                    result.authors.append(name)
                if "toimetaja" == role:
                    result.editors.append(name)
                elif "väljaandja" == role:
                    result.publishers.append(name)
                elif "koostaja" == role:
                    result.compilers.append(name)
                elif "illustreerija" == role:
                    result.illustrators.append(name)
                elif "tõlkija" == role:
                    result.translators.append(name)
                elif "kujundaja" == role:
                    result.designers.append(name)
                elif "fotograaf" == role:
                    result.photographers.append(name)

        results.append(result)

    return results
