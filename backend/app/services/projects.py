"""The Palm Hills projects a resident can select as their location.

**This list is reference data, not verified policy data.** The regulations
dataset carries no project list — every rule in v1.0 is community-wide, and the
only compound token that appears anywhere in it is `north_coast` (on the beach
facility). So unlike a fine or a rule, the names below are not transcribed from
the source document; they are a starting list that Community Management is
expected to confirm and correct.

It lives here, served over the API, rather than being compiled into the app, for
exactly that reason: correcting a project name or adding a new launch must not
require shipping a new build to every resident.

`compound` is the scoping token sent back on requests, and it is deliberately
**not** always the project's own id. Rule and facility scoping in v1.0 only
distinguishes the North Coast from everywhere else, so the North Coast projects
all resolve to `north_coast`; that is what keeps the beach facility and its rules
in scope for a Hacienda resident and out of scope for a Cairo one. When the
dataset starts scoping rules per project, these tokens become per-project and
nothing else has to change.
"""

from __future__ import annotations

from dataclasses import dataclass

CAIRO_WEST = "cairo_west"
CAIRO_EAST = "cairo_east"
NORTH_COAST = "north_coast"
OTHER = "other"


@dataclass(frozen=True)
class Project:
    id: str
    name_en: str
    name_ar: str
    region: str
    #: The value the client sends as `compound`. See the module docstring.
    compound: str


#: Ordered by region, then alphabetically inside it, so the picker groups the way
#: a resident thinks about the map rather than the way a database sorts.
PROJECTS: tuple[Project, ...] = (
    # --- West Cairo / 6th of October -----------------------------------
    Project("palm_hills_october", "Palm Hills October", "بالم هيلز أكتوبر", CAIRO_WEST, "palm_hills_october"),
    Project("palm_hills_golf_extension", "Palm Hills Golf Extension", "بالم هيلز جولف إكستنشن", CAIRO_WEST, "palm_hills_golf_extension"),
    Project("palm_hills_golf_views", "Golf Views", "جولف فيوز", CAIRO_WEST, "palm_hills_golf_views"),
    Project("palm_valley", "Palm Valley", "بالم فالي", CAIRO_WEST, "palm_valley"),
    Project("palm_parks", "Palm Parks", "بالم باركس", CAIRO_WEST, "palm_parks"),
    Project("the_crown", "The Crown", "ذا كراون", CAIRO_WEST, "the_crown"),
    Project("badya", "Badya", "بادية", CAIRO_WEST, "badya"),
    Project("woodville", "Woodville", "وودفيل", CAIRO_WEST, "woodville"),
    Project("village_gate", "Village Gate", "فيلدج جيت", CAIRO_WEST, "village_gate"),
    Project("village_gardens", "Village Gardens", "فيلدج جاردنز", CAIRO_WEST, "village_gardens"),
    Project("village_avenue", "Village Avenue", "فيلدج أفنيو", CAIRO_WEST, "village_avenue"),
    # --- East Cairo / New Cairo ----------------------------------------
    Project("palm_hills_new_cairo", "Palm Hills New Cairo", "بالم هيلز نيو كايرو", CAIRO_EAST, "palm_hills_new_cairo"),
    Project("capital_gardens", "Capital Gardens", "كابيتال جاردنز", CAIRO_EAST, "capital_gardens"),
    Project("palm_hills_katameya", "Palm Hills Katameya", "بالم هيلز القطامية", CAIRO_EAST, "palm_hills_katameya"),
    Project("palm_hills_katameya_extension", "Katameya Extension", "القطامية إكستنشن", CAIRO_EAST, "palm_hills_katameya_extension"),
    Project("botanica", "Botanica", "بوتانيكا", CAIRO_EAST, "botanica"),
    # --- North Coast ----------------------------------------------------
    # All resolve to `north_coast`: see the module docstring.
    Project("hacienda_bay", "Hacienda Bay", "هاسيندا باي", NORTH_COAST, NORTH_COAST),
    Project("hacienda_white", "Hacienda White", "هاسيندا وايت", NORTH_COAST, NORTH_COAST),
    Project("hacienda_red", "Hacienda Red", "هاسيندا ريد", NORTH_COAST, NORTH_COAST),
    Project("hacienda_blue", "Hacienda Blue", "هاسيندا بلو", NORTH_COAST, NORTH_COAST),
    Project("hacienda_west", "Hacienda West", "هاسيندا ويست", NORTH_COAST, NORTH_COAST),
    Project("hacienda_waters", "Hacienda Waters", "هاسيندا ووترز", NORTH_COAST, NORTH_COAST),
    # --- Alexandria -----------------------------------------------------
    Project("palm_hills_alexandria", "Palm Hills Alexandria", "بالم هيلز الإسكندرية", OTHER, "palm_hills_alexandria"),
)

#: Region labels for the picker's group headers.
REGIONS: dict[str, tuple[str, str]] = {
    CAIRO_WEST: ("West Cairo & 6th of October", "غرب القاهرة و٦ أكتوبر"),
    CAIRO_EAST: ("New Cairo & Katameya", "القاهرة الجديدة والقطامية"),
    NORTH_COAST: ("North Coast", "الساحل الشمالي"),
    OTHER: ("Other", "أخرى"),
}


def list_projects() -> list[Project]:
    return list(PROJECTS)


def find(project_id: str) -> Project | None:
    return next((p for p in PROJECTS if p.id == project_id), None)
