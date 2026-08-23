"""Low-level, layout-preserving Word Content Control population.

``python-docx`` does not expose structured document tags (SDTs).  This module
therefore edits the template package directly: it copies every ZIP part and
only changes text nodes inside tag-addressed SDTs.  Tables, cell properties,
paragraph properties, runs, borders, shading, and the SDT wrappers remain in
place.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"w": WORD_NS}
DOCUMENT_PART = "word/document.xml"


class ContentControlNotFoundError(RuntimeError):
    """Raised when a requested Word Content Control tag cannot be found."""


class DocumentReplaceError(RuntimeError):
    """Raised when Windows prevents an updated DOCX from replacing its source."""


@dataclass(frozen=True)
class ContentControl:
    """A content-control location within a WordprocessingML package part."""

    part_name: str
    element: etree._Element

    @property
    def tag(self) -> str:
        return control_tag(self.element)


def qn(local_name: str) -> str:
    """Return a qualified WordprocessingML element or attribute name."""

    return f"{{{WORD_NS}}}{local_name}"


def read_document_root(docx_path: Path) -> etree._Element:
    """Load only the main document XML for structural validation."""

    with ZipFile(docx_path) as package:
        return etree.fromstring(package.read(DOCUMENT_PART))


def find_content_controls(root: etree._Element, part_name: str = DOCUMENT_PART) -> list[ContentControl]:
    """Return every SDT in a parsed WordprocessingML part."""

    return [ContentControl(part_name, element) for element in root.xpath(".//w:sdt", namespaces=NS)]


def control_tag(control: etree._Element) -> str:
    """Read the stable ``w:tag`` identifier for an SDT, if it has one."""

    tag = control.find("w:sdtPr/w:tag", namespaces=NS)
    return "" if tag is None else str(tag.get(qn("val"), ""))


def control_text(control: etree._Element) -> str:
    """Return visible text currently inside an SDT without altering it."""

    return "".join(control.xpath(".//w:sdtContent//w:t/text()", namespaces=NS))


def find_control_by_tag(docx_path: Path, tag: str) -> ContentControl:
    """Find a single tag across document, headers, footers, and related parts."""

    matches = _controls_by_tag(docx_path).get(tag, [])
    if not matches:
        raise ContentControlNotFoundError(f"Missing Content Control tag: {tag}")
    if len(matches) > 1:
        raise ContentControlNotFoundError(f"Content Control tag appears {len(matches)} times: {tag}")
    return matches[0]


def read_content_control_values(docx_path: Path) -> dict[str, str]:
    """Read unique tag values from an editable resume document.

    This is the reverse half of the resume workflow: users edit the retained
    ``portfolio/resume-working.docx`` in Word, then the sync command reads its content
    controls back into the canonical JSON data.
    """

    controls_by_tag = _controls_by_tag(docx_path)
    duplicates = sorted(tag for tag, controls in controls_by_tag.items() if len(controls) != 1)
    if duplicates:
        raise ContentControlNotFoundError("Content Control tag is duplicated: " + ", ".join(duplicates))
    return {tag: control_text(controls[0].element).strip() for tag, controls in controls_by_tag.items()}


def render_word_template(
    template_path: Path, output_path: Path, values: dict[str, str], remove_blank_tags: set[str] | None = None
) -> list[str]:
    """Populate a DOCX template by SDT tag while preserving its layout package.

    Every source package entry is copied unchanged except XML parts containing a
    value to replace. Text is changed inside existing ``w:sdtContent`` nodes;
    no tables, cells, paragraphs, or SDT wrappers are recreated.
    """

    controls_by_tag = _controls_by_tag(template_path)
    missing = sorted(tag for tag in values if tag not in controls_by_tag)
    if missing:
        raise ContentControlNotFoundError("Missing Content Control tag: " + ", ".join(missing))
    duplicate = sorted(tag for tag in values if len(controls_by_tag[tag]) != 1)
    if duplicate:
        raise ContentControlNotFoundError("Content Control tag is duplicated: " + ", ".join(duplicate))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    modified_parts, removed_tags = _populate_parts(template_path, values, remove_blank_tags or set())
    replace_in_place = template_path.resolve() == output_path.resolve()
    destination = output_path
    if replace_in_place:
        with NamedTemporaryFile(prefix=f"{output_path.stem}-", suffix=".docx", dir=output_path.parent, delete=False) as handle:
            destination = Path(handle.name)
    try:
        with ZipFile(template_path) as source, ZipFile(destination, "w", compression=ZIP_DEFLATED) as target:
            for info in source.infolist():
                payload = modified_parts.get(info.filename, source.read(info.filename))
                target.writestr(info, payload, compress_type=info.compress_type)
        if replace_in_place:
            _replace_document(destination, output_path)
    finally:
        if replace_in_place and destination.exists():
            destination.unlink()
    return sorted(removed_tags)


def replace_static_paragraph_text(docx_path: Path, old_text: str, new_text: str) -> None:
    """Replace one non-control paragraph while preserving its OOXML layout.

    Static document labels intentionally have no JSON counterpart. This helper
    makes a narrow, exact-match layout correction possible without rebuilding
    the document or touching its Content Controls.
    """

    modified: dict[str, bytes] = {}
    replacements = 0
    with ZipFile(docx_path) as package:
        for part_name in _word_xml_parts(package.namelist()):
            payload = package.read(part_name)
            root = etree.fromstring(payload)
            changed = False
            for paragraph in root.xpath(".//w:p", namespaces=NS):
                text_nodes = list(paragraph.xpath(".//w:t", namespaces=NS))
                if "".join(node.text or "" for node in text_nodes) != old_text:
                    continue
                _set_text(text_nodes[0], new_text)
                for node in text_nodes[1:]:
                    _set_text(node, "")
                replacements += 1
                changed = True
            if changed:
                modified[part_name] = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
        if replacements != 1:
            raise ContentControlNotFoundError(
                f"Expected one static Word paragraph containing {old_text!r}; found {replacements}"
            )

        with NamedTemporaryFile(prefix=f"{docx_path.stem}-", suffix=".docx", dir=docx_path.parent, delete=False) as handle:
            destination = Path(handle.name)
        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as target:
            for info in package.infolist():
                payload = modified.get(info.filename, package.read(info.filename))
                target.writestr(info, payload, compress_type=info.compress_type)
    try:
        _replace_document(destination, docx_path)
    finally:
        if destination.exists():
            destination.unlink()


def _replace_document(temporary_path: Path, output_path: Path) -> None:
    """Replace an editable DOCX, allowing brief Windows lock-release delays.

    Microsoft Word can remain as a background process after its window closes,
    and Explorer's preview pane can briefly hold the same handle.  Retry a few
    times for a transient release, then leave the original untouched and give a
    direct recovery instruction.  The caller always removes the temporary file.
    """

    last_error: PermissionError | None = None
    for attempt in range(5):
        try:
            temporary_path.replace(output_path)
            return
        except PermissionError as error:
            last_error = error
            if attempt < 4:
                time.sleep(0.25)
    raise DocumentReplaceError(
        f"Could not update {output_path.name}; Windows still has it locked. "
        "Close any Word document and File Explorer preview, then end any background WINWORD.EXE "
        "process only after confirming it has no unsaved work."
    ) from last_error


def fix_page_two_project_layout(docx_path: Path) -> None:
    """Repair the fixed-width page-two project table without touching controls.

    The original table carried an unused third grid column and a negative
    indent. Its visible header overflowed the page while project dates had too
    little room. This normalizes the grid to the document's usable 10,656-DXA
    width and retains every row, style, and Content Control in place.
    """

    with ZipFile(docx_path) as package:
        root = etree.fromstring(package.read(DOCUMENT_PART))
        table = next(
            (
                candidate
                for candidate in root.xpath("./w:body/w:tbl", namespaces=NS)
                if "SELECTED PROJECT PORTFOLIO" in "".join(candidate.xpath(".//w:t/text()", namespaces=NS))
            ),
            None,
        )
        if table is None:
            raise ContentControlNotFoundError("Could not locate the page-two selected-project table")

        rows = table.xpath("./w:tr", namespaces=NS)
        if len(rows) != 11:
            raise ContentControlNotFoundError(
                f"Page-two selected-project table has {len(rows)} rows; expected 11 before layout repair"
            )
        _set_table_width(table, 10656)
        _set_table_indent(table, 0)
        grid = table.xpath("./w:tblGrid/w:gridCol", namespaces=NS)
        if len(grid) != 3:
            raise ContentControlNotFoundError(
                f"Page-two selected-project table has {len(grid)} grid columns; expected 3 before layout repair"
            )
        for column, width in zip(grid, (5000, 3300, 2356), strict=True):
            column.set(qn("w"), str(width))

        for index in (0, 1):
            left, right = _two_cells(rows[index])
            _set_cell_width(left, 5000)
            _set_cell_width(right, 5656)
            _set_grid_span(right, 2)

        _set_full_width_row(rows[2], 3)
        for index in (3, 5, 7, 9):
            project, dates = _two_cells(rows[index])
            _set_cell_width(project, 8300)
            _set_grid_span(project, 2)
            _set_cell_width(dates, 2356)
        for index in (4, 6, 8, 10):
            _set_full_width_row(rows[index], 3)

        payload = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
        with NamedTemporaryFile(prefix=f"{docx_path.stem}-", suffix=".docx", dir=docx_path.parent, delete=False) as handle:
            destination = Path(handle.name)
        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as target:
            for info in package.infolist():
                target.writestr(
                    info,
                    payload if info.filename == DOCUMENT_PART else package.read(info.filename),
                    compress_type=info.compress_type,
                )
    destination.replace(docx_path)


def _controls_by_tag(docx_path: Path) -> dict[str, list[ContentControl]]:
    controls: dict[str, list[ContentControl]] = {}
    with ZipFile(docx_path) as package:
        for part_name in _word_xml_parts(package.namelist()):
            payload = package.read(part_name)
            if b"<w:sdt" not in payload:
                continue
            root = etree.fromstring(payload)
            for control in find_content_controls(root, part_name):
                if control.tag:
                    controls.setdefault(control.tag, []).append(control)
    return controls


def _populate_parts(
    template_path: Path, values: dict[str, str], remove_blank_tags: set[str]
) -> tuple[dict[str, bytes], set[str]]:
    modified: dict[str, bytes] = {}
    removed: set[str] = set()
    with ZipFile(template_path) as package:
        for part_name in _word_xml_parts(package.namelist()):
            payload = package.read(part_name)
            if b"<w:sdt" not in payload:
                continue
            root = etree.fromstring(payload)
            changed = False
            for control in find_content_controls(root, part_name):
                tag = control.tag
                if tag not in values:
                    continue
                if tag in remove_blank_tags and not values[tag]:
                    removable = control.element.getparent()
                    while removable is not None and removable.tag not in {qn("tr"), qn("p")}:
                        removable = removable.getparent()
                    if removable is not None and removable.getparent() is not None:
                        removable.getparent().remove(removable)
                        removed.add(tag)
                    continue
                replace_control_text(control.element, values[tag])
                changed = True
            if changed:
                modified[part_name] = etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)
    return modified, removed


def replace_control_text(control: etree._Element, value: str) -> None:
    """Replace only visible text inside an existing plain or rich-text SDT.

    Existing text nodes are retained so their runs retain font and character
    properties. Newlines are represented as ``w:br`` elements in the first
    styled run, which also makes simple rich-text controls safe to populate.
    """

    text_nodes = list(control.xpath(".//w:sdtContent//w:t", namespaces=NS))
    if not text_nodes:
        text_nodes = [_create_text_node(control)]

    lines = str(value).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    first = text_nodes[0]
    _set_text(first, lines[0])
    for node in text_nodes[1:]:
        _set_text(node, "")

    run = first.getparent()
    if run is None or run.tag != qn("r"):
        return
    for line in lines[1:]:
        run.append(etree.Element(qn("br")))
        added_text = etree.SubElement(run, qn("t"))
        _set_text(added_text, line)


def _create_text_node(control: etree._Element) -> etree._Element:
    content = control.find("w:sdtContent", namespaces=NS)
    if content is None:
        raise ContentControlNotFoundError("Content Control has no w:sdtContent")
    paragraph = content.find(".//w:p", namespaces=NS)
    if paragraph is None:
        paragraph = etree.SubElement(content, qn("p"))
    run = etree.SubElement(paragraph, qn("r"))
    return etree.SubElement(run, qn("t"))


def _set_table_width(table: etree._Element, width: int) -> None:
    table_width = table.find("w:tblPr/w:tblW", namespaces=NS)
    if table_width is None:
        raise ContentControlNotFoundError("Page-two selected-project table has no table width")
    table_width.set(qn("w"), str(width))
    table_width.set(qn("type"), "dxa")


def _set_table_indent(table: etree._Element, indent: int) -> None:
    table_indent = table.find("w:tblPr/w:tblInd", namespaces=NS)
    if table_indent is None:
        raise ContentControlNotFoundError("Page-two selected-project table has no table indent")
    table_indent.set(qn("w"), str(indent))
    table_indent.set(qn("type"), "dxa")


def _two_cells(row: etree._Element) -> tuple[etree._Element, etree._Element]:
    cells = row.xpath("./w:tc", namespaces=NS)
    if len(cells) != 2:
        raise ContentControlNotFoundError(f"Expected a two-cell page-two table row; found {len(cells)}")
    return cells[0], cells[1]


def _set_full_width_row(row: etree._Element, grid_span: int) -> None:
    cells = row.xpath("./w:tc", namespaces=NS)
    if len(cells) != 1:
        raise ContentControlNotFoundError(f"Expected a full-width page-two table row; found {len(cells)} cells")
    _set_cell_width(cells[0], 10656)
    _set_grid_span(cells[0], grid_span)


def _set_cell_width(cell: etree._Element, width: int) -> None:
    cell_width = cell.find("w:tcPr/w:tcW", namespaces=NS)
    if cell_width is None:
        raise ContentControlNotFoundError("Page-two selected-project cell has no width")
    cell_width.set(qn("w"), str(width))
    cell_width.set(qn("type"), "dxa")


def _set_grid_span(cell: etree._Element, span: int) -> None:
    properties = cell.find("w:tcPr", namespaces=NS)
    if properties is None:
        raise ContentControlNotFoundError("Page-two selected-project cell has no properties")
    grid_span = properties.find("w:gridSpan", namespaces=NS)
    if grid_span is None:
        grid_span = etree.Element(qn("gridSpan"))
        properties.insert(0, grid_span)
    grid_span.set(qn("val"), str(span))


def _set_text(node: etree._Element, value: str) -> None:
    node.text = value
    if value[:1].isspace() or value[-1:].isspace():
        node.set(f"{{{XML_NS}}}space", "preserve")
    else:
        node.attrib.pop(f"{{{XML_NS}}}space", None)


def _word_xml_parts(names: Iterable[str]) -> list[str]:
    return [name for name in names if name.startswith("word/") and name.endswith(".xml")]
