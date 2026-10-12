"""Modele de particules XSD local utilise pour contraindre l'emission XML."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re
from typing import TypeAlias

import lxml.etree as etree

_XS_NS = "http://www.w3.org/2001/XMLSchema"
_XS = f"{{{_XS_NS}}}"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_NS = {"xs": _XS_NS}
_SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "s1000d_schemas"
_SCHEMA_STEMS = {
    "descriptive": "descript",
    "description": "descript",
    "descript": "descript",
    "procedural": "proced",
    "procedure": "proced",
    "proced": "proced",
    "ipd": "ipd",
}
QName = tuple[str | None, str]
XmlElement: TypeAlias = etree._Element


@dataclass(frozen=True)
class Particle:
    kind: str
    min_occurs: int = 1
    max_occurs: int | None = 1
    name: QName | None = None
    declaration: XmlElement | None = field(default=None, compare=False)
    children: tuple[Particle, ...] = ()


@dataclass(frozen=True)
class AttributeModel:
    name: QName
    required: bool
    type_name: QName | None
    inline_type: XmlElement | None = field(default=None, compare=False)
    fixed: str | None = None
    default: str | None = None


@dataclass(frozen=True)
class SimpleFacets:
    enumerations: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    length: int | None = None
    min_length: int | None = None
    max_length: int | None = None


@dataclass
class ConstraintReport:
    violations: list[dict] = field(default_factory=list)
    provisional_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _MatchItem:
    element: XmlElement
    synthetic: bool
    declaration: XmlElement | None = field(default=None, compare=False)


@dataclass(frozen=True)
class _Match:
    items: tuple[_MatchItem, ...]
    remaining: tuple[XmlElement, ...]
    matched: int
    generated: int


MatchCache = dict[tuple[int, tuple[int, ...]], list[_Match]]


def _local_name(node: XmlElement) -> str:
    return etree.QName(node).localname


def _xml_qname(name: QName) -> str:
    namespace, local = name
    return f"{{{namespace}}}{local}" if namespace else local


def _element_qname(element: XmlElement) -> QName:
    name = etree.QName(element)
    return name.namespace, name.localname


def _occurrences(node: XmlElement) -> tuple[int, int | None]:
    minimum = int(node.get("minOccurs", "1"))
    maximum = node.get("maxOccurs", "1")
    return minimum, None if maximum == "unbounded" else int(maximum)


class XsdModel:
    def __init__(self, issue: str, dm_type: str, path: Path) -> None:
        self.issue = issue
        self.dm_type = dm_type
        self.path = path
        self.documents: list[tuple[Path, etree._ElementTree]] = []
        self._load_schema(path, set())
        self.schema_root = self.documents[0][1].getroot()
        self.elements: dict[QName, XmlElement] = {}
        self.types: dict[QName, XmlElement] = {}
        self.simple_types: dict[QName, XmlElement] = {}
        self.groups: dict[QName, XmlElement] = {}
        self.attributes: dict[QName, XmlElement] = {}
        self.attribute_groups: dict[QName, XmlElement] = {}
        self._index_components()
        self._particle_cache: dict[int, Particle | None] = {}
        self._attribute_cache: dict[int, tuple[AttributeModel, ...]] = {}
        self._probes, self._probe_schema = self._build_value_probes()

    def _load_schema(self, path: Path, seen: set[Path]) -> None:
        path = path.resolve()
        if path in seen or not path.is_file():
            return
        seen.add(path)
        tree = etree.parse(str(path))
        root = tree.getroot()
        self.documents.append((path, tree))
        for dependency in root.xpath("./xs:import|./xs:include|./xs:redefine", namespaces=_NS):
            location = dependency.get("schemaLocation")
            if location:
                self._load_schema(path.parent / location, seen)

    def _index_components(self) -> None:
        component_maps = {
            "element": self.elements,
            "complexType": self.types,
            "simpleType": self.simple_types,
            "group": self.groups,
            "attribute": self.attributes,
            "attributeGroup": self.attribute_groups,
        }
        for _path, tree in self.documents:
            root = tree.getroot()
            namespace = root.get("targetNamespace")
            for child in root:
                if not isinstance(child.tag, str) or not child.get("name"):
                    continue
                local = _local_name(child)
                destination = component_maps.get(local)
                if destination is not None:
                    destination[(namespace, child.get("name"))] = child

    def _resolve_qname(self, node: XmlElement, value: str | None) -> QName | None:
        if not value:
            return None
        if ":" not in value:
            return node.nsmap.get(None), value
        prefix, local = value.split(":", 1)
        return node.nsmap.get(prefix), local

    def _element_declaration(self, node: XmlElement) -> tuple[QName, XmlElement]:
        reference = node.get("ref")
        if reference:
            name = self._resolve_qname(node, reference) or (None, reference)
            return name, self.elements.get(name, node)
        root = node.getroottree().getroot()
        namespace = root.get("targetNamespace")
        form = node.get("form", root.get("elementFormDefault", "unqualified"))
        name = (namespace if form == "qualified" else None, node.get("name", ""))
        return name, node

    def _parse_particle(
        self,
        node: XmlElement,
        group_stack: tuple[QName, ...] = (),
    ) -> Particle:
        kind = _local_name(node)
        minimum, maximum = _occurrences(node)
        if kind == "element":
            name, declaration = self._element_declaration(node)
            return Particle("element", minimum, maximum, name, declaration)
        if kind == "group":
            reference = node.get("ref")
            if reference:
                name = self._resolve_qname(node, reference) or (None, reference)
                definition = self.groups.get(name)
                if definition is None or name in group_stack:
                    return Particle("empty", minimum, maximum)
                body = next(
                    (
                        child for child in definition
                        if isinstance(child.tag, str)
                        and _local_name(child) in {"sequence", "choice", "all"}
                    ),
                    None,
                )
                children = (self._parse_particle(body, group_stack + (name,)),) if body is not None else ()
            else:
                children = tuple(
                    self._parse_particle(child, group_stack)
                    for child in node
                    if isinstance(child.tag, str)
                    and _local_name(child) in {"sequence", "choice", "all", "element", "group"}
                )
            return Particle("group", minimum, maximum, children=children)
        if kind in {"sequence", "choice", "all"}:
            children = tuple(
                self._parse_particle(child, group_stack)
                for child in node
                if isinstance(child.tag, str)
                and _local_name(child) in {"sequence", "choice", "all", "element", "group", "any"}
            )
            return Particle(kind, minimum, maximum, children=children)
        if kind == "any":
            return Particle("any", minimum, maximum)
        return Particle("empty", minimum, maximum)

    def _type_node(self, declaration: XmlElement) -> XmlElement | None:
        inline = next(
            (
                child for child in declaration
                if isinstance(child.tag, str)
                and _local_name(child) in {"complexType", "simpleType"}
            ),
            None,
        )
        if inline is not None:
            return inline
        type_name = self._resolve_qname(declaration, declaration.get("type"))
        if type_name is None:
            return None
        type_node = self.types.get(type_name)
        return type_node if type_node is not None else self.simple_types.get(type_name)

    def _particle_for(self, declaration: XmlElement) -> Particle | None:
        cache_key = id(declaration)
        if cache_key in self._particle_cache:
            return self._particle_cache[cache_key]
        type_node = self._type_node(declaration)
        particle_node = None
        if type_node is not None and _local_name(type_node) == "complexType":
            particle_node = next(
                (
                    child for child in type_node
                    if isinstance(child.tag, str)
                    and _local_name(child) in {"sequence", "choice", "all", "group"}
                ),
                None,
            )
        particle = self._parse_particle(particle_node) if particle_node is not None else None
        self._particle_cache[cache_key] = particle
        return particle

    def _attribute_from_node(self, node: XmlElement) -> AttributeModel:
        reference = node.get("ref")
        global_node = None
        if reference:
            name = self._resolve_qname(node, reference) or (None, reference)
            global_node = self.attributes.get(name)
        else:
            root = node.getroottree().getroot()
            namespace = root.get("targetNamespace")
            form = node.get("form", root.get("attributeFormDefault", "unqualified"))
            name = (namespace if form == "qualified" else None, node.get("name", ""))
        source = global_node if global_node is not None else node
        inline = next(
            (child for child in source if isinstance(child.tag, str) and _local_name(child) == "simpleType"),
            None,
        )
        type_name = self._resolve_qname(source, source.get("type"))
        fixed = node.get("fixed", source.get("fixed"))
        default = node.get("default", source.get("default"))
        use = node.get("use", source.get("use", "optional"))
        return AttributeModel(name, use == "required", type_name, inline, fixed, default)

    def _attributes_for_group(self, name: QName, seen: tuple[QName, ...] = ()) -> list[AttributeModel]:
        if name in seen:
            return []
        group = self.attribute_groups.get(name)
        if group is None:
            return []
        return self._attributes_in(group, seen + (name,))

    def _attributes_in(
        self,
        container: XmlElement,
        group_stack: tuple[QName, ...] = (),
    ) -> list[AttributeModel]:
        result: list[AttributeModel] = []
        for child in container:
            if not isinstance(child.tag, str):
                continue
            kind = _local_name(child)
            if kind == "attribute":
                result.append(self._attribute_from_node(child))
            elif kind == "attributeGroup" and child.get("ref"):
                reference = self._resolve_qname(child, child.get("ref"))
                if reference:
                    result.extend(self._attributes_for_group(reference, group_stack))
        return result

    def _attributes_for(self, declaration: XmlElement) -> tuple[AttributeModel, ...]:
        cache_key = id(declaration)
        if cache_key in self._attribute_cache:
            return self._attribute_cache[cache_key]
        type_node = self._type_node(declaration)
        if type_node is None or _local_name(type_node) != "complexType":
            self._attribute_cache[cache_key] = ()
            return ()
        simple_content = next(
            (child for child in type_node if isinstance(child.tag, str) and _local_name(child) == "simpleContent"),
            None,
        )
        container = type_node
        if simple_content is not None:
            container = next(
                (
                    child for child in simple_content
                    if isinstance(child.tag, str) and _local_name(child) in {"extension", "restriction"}
                ),
                simple_content,
            )
        attributes = tuple(self._attributes_in(container))
        self._attribute_cache[cache_key] = attributes
        return attributes

    def _simple_value_type(
        self,
        declaration: XmlElement,
    ) -> tuple[QName | None, XmlElement | None]:
        type_node = self._type_node(declaration)
        if type_node is None:
            return None, None
        kind = _local_name(type_node)
        if kind == "simpleType":
            type_name = self._resolve_qname(declaration, declaration.get("type"))
            return type_name, type_node if declaration.get("type") is None else None
        if kind == "complexType":
            simple_content = next(
                (child for child in type_node if isinstance(child.tag, str) and _local_name(child) == "simpleContent"),
                None,
            )
            if simple_content is not None:
                derivation = next(
                    (
                        child for child in simple_content
                        if isinstance(child.tag, str) and _local_name(child) in {"extension", "restriction"}
                    ),
                    None,
                )
                if derivation is not None:
                    return self._resolve_qname(derivation, derivation.get("base")), None
        return None, None

    def facets_for(
        self,
        type_name: QName | None,
        inline_type: XmlElement | None = None,
    ) -> SimpleFacets:
        if inline_type is not None:
            current = inline_type
        elif type_name is not None:
            current = self.simple_types.get(type_name)
        else:
            current = None
        enumerations: list[str] = []
        patterns: list[str] = []
        lengths: list[int] = []
        minimums: list[int] = []
        maximums: list[int] = []
        visited: set[int] = set()
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            restriction = next(
                (child for child in current if isinstance(child.tag, str) and _local_name(child) == "restriction"),
                None,
            )
            if restriction is None:
                break
            for facet in restriction:
                if not isinstance(facet.tag, str):
                    continue
                name = _local_name(facet)
                value = facet.get("value")
                if value is None:
                    continue
                if name == "enumeration":
                    enumerations.append(value)
                elif name == "pattern":
                    patterns.append(value)
                elif name == "length":
                    lengths.append(int(value))
                elif name == "minLength":
                    minimums.append(int(value))
                elif name == "maxLength":
                    maximums.append(int(value))
            base = self._resolve_qname(restriction, restriction.get("base"))
            inline_base = next(
                (child for child in restriction if isinstance(child.tag, str) and _local_name(child) == "simpleType"),
                None,
            )
            current = inline_base
            if current is None and base is not None:
                current = self.simple_types.get(base)
        return SimpleFacets(
            enumerations=tuple(dict.fromkeys(enumerations)),
            patterns=tuple(dict.fromkeys(patterns)),
            length=lengths[0] if lengths else None,
            min_length=max(minimums) if minimums else None,
            max_length=min(maximums) if maximums else None,
        )

    def _qualified_type(self, name: QName) -> tuple[str, dict[str | None, str]]:
        namespace, local = name
        namespaces = dict(self.schema_root.nsmap)
        if namespace is None:
            return local, namespaces
        for prefix, uri in namespaces.items():
            if uri == namespace and prefix:
                return f"{prefix}:{local}", namespaces
        prefix = "xsdprobe"
        namespaces[prefix] = namespace
        return f"{prefix}:{local}", namespaces

    def _build_value_probes(self) -> tuple[dict[tuple[str, object], str], etree.XMLSchema]:
        probe_tree = deepcopy(self.documents[0][1])
        probe_root = probe_tree.getroot()
        accessible_namespaces = {probe_root.get("targetNamespace")}
        accessible_namespaces.update(
            dependency.get("namespace")
            for dependency in probe_root.xpath("./xs:import", namespaces=_NS)
            if dependency.get("namespace")
        )
        probes: dict[tuple[str, object], str] = {}
        probe_index = 0

        def add_probe(
            key: tuple[str, object],
            *,
            type_name: QName | None = None,
            inline_type: XmlElement | None = None,
        ) -> None:
            nonlocal probe_index
            if key in probes:
                return
            probe_name = f"__xsd_value_{probe_index}"
            probe_index += 1
            if type_name is not None:
                lexical, namespaces = self._qualified_type(type_name)
                element = etree.Element(_XS + "element", name=probe_name, type=lexical, nsmap=namespaces)
            else:
                element = etree.Element(_XS + "element", name=probe_name, nsmap=self.schema_root.nsmap)
                if inline_type is not None:
                    element.append(deepcopy(inline_type))
            probe_root.append(element)
            probes[key] = probe_name

        for type_name in self.simple_types:
            if type_name[0] not in accessible_namespaces:
                continue
            add_probe(("named", type_name), type_name=type_name)
        builtin_types: set[QName] = set()
        inline_types: list[XmlElement] = []
        for _path, tree in self.documents:
            for node in tree.getroot().iter():
                if not isinstance(node.tag, str):
                    continue
                node_namespace = node.getroottree().getroot().get("targetNamespace")
                if (
                    _local_name(node) == "simpleType"
                    and not node.get("name")
                    and node_namespace in accessible_namespaces
                ):
                    inline_types.append(node)
                for attribute in ("type", "base", "itemType", "memberTypes"):
                    lexical = node.get(attribute)
                    if not lexical:
                        continue
                    for value in lexical.split():
                        name = self._resolve_qname(node, value)
                        if name and name[0] == _XS_NS:
                            builtin_types.add(name)
        for type_name in sorted(builtin_types):
            add_probe(("named", type_name), type_name=type_name)
        for inline_type in inline_types:
            add_probe(("inline", id(inline_type)), inline_type=inline_type)
        entity_probe_name = "__xsd_entity_attribute_probe"
        entity_probe = etree.Element(
            _XS + "element",
            name=entity_probe_name,
            nsmap=self.schema_root.nsmap,
        )
        entity_type = etree.SubElement(entity_probe, _XS + "complexType")
        etree.SubElement(
            entity_type,
            _XS + "attribute",
            name="value",
            type="xs:ENTITY",
            use="required",
        )
        probe_root.append(entity_probe)
        probes[("entity_attribute", (_XS_NS, "ENTITY"))] = entity_probe_name
        return probes, etree.XMLSchema(probe_tree)

    def _value_is_valid(
        self,
        type_name: QName | None,
        inline_type: XmlElement | None,
        value: str,
    ) -> bool:
        if type_name is None and inline_type is None:
            return True
        key: tuple[str, object] = ("named", type_name) if type_name is not None else ("inline", id(inline_type))
        probe_name = self._probes.get(key)
        if probe_name is None:
            return True
        if type_name == (_XS_NS, "ENTITY"):
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", value):
                return False
            entity_probe = self._probes[("entity_attribute", type_name)]
            source = (
                f'<!DOCTYPE {entity_probe} ['
                '<!NOTATION xsdprobe SYSTEM "image/jpeg">'
                f'<!ENTITY {value} SYSTEM "xsd-probe.jpg" NDATA xsdprobe>'
                f']><{entity_probe} value="{value}"/>'
            )
            try:
                entity_probe = etree.fromstring(
                    source.encode("utf-8"),
                    etree.XMLParser(load_dtd=True, resolve_entities=False, no_network=True),
                )
            except etree.XMLSyntaxError:
                return False
            return self._probe_schema.validate(entity_probe)
        element = etree.Element(probe_name)
        element.text = value
        return self._probe_schema.validate(element)

    def accepts_value(
        self,
        type_name: QName | None,
        value: str,
        inline_type: XmlElement | None = None,
    ) -> bool:
        return self._value_is_valid(type_name, inline_type, value)

    def _pattern_candidates(self, pattern: str) -> list[str]:
        candidates: list[str] = []
        has_digits = "0-9" in pattern or r"\d" in pattern
        has_upper = "A-Z" in pattern
        has_lower = "a-z" in pattern
        for length in range(1, 17):
            if has_digits:
                candidates.append("0" * length)
            if has_upper:
                candidates.append("Z" * length)
            if has_lower:
                candidates.append("z" * length)
            if has_upper and has_digits:
                candidates.extend(("Z0" * length, "A" + "0" * length))
        literal = re.sub(r"\\[a-zA-Z]|\[[^]]+\]|[(){}+*?.|^$]", "", pattern)
        if literal:
            candidates.append(literal)
        return candidates

    def provisional_value(
        self,
        type_name: QName | None,
        inline_type: XmlElement | None = None,
        *,
        fixed: str | None = None,
        default: str | None = None,
    ) -> str | None:
        facets = self.facets_for(type_name, inline_type)
        candidates: list[str] = []
        if fixed is not None:
            candidates.append(fixed)
        if default is not None:
            candidates.append(default)
        candidates.extend(facets.enumerations)
        candidates.extend(("A REMPLACER", "ZZ", "ZZZ", "Z", "A", "AA", "AAA"))
        for pattern in facets.patterns:
            candidates.extend(self._pattern_candidates(pattern))
        candidates.extend(("0", "1", "00", "01", "001", "000", "0000", "00000"))
        candidates.extend(("2020-01-01", "1970-01-01", "false", "0.0", "AA=="))
        for value in dict.fromkeys(candidates):
            if self._value_is_valid(type_name, inline_type, value):
                return value
        return None

    def constrain(self, root: XmlElement) -> ConstraintReport:
        report = ConstraintReport()
        name = _element_qname(root)
        declaration = self.elements.get(name)
        if declaration is None:
            report.violations.append(self._violation("/", f"La racine {name[1]} n'est pas declaree dans le XSD."))
            return report
        self._constrain_element(root, declaration, "/dmodule", report, 0)
        report.provisional_fields = list(dict.fromkeys(report.provisional_fields))
        return report

    def _violation(self, path: str, message: str) -> dict:
        return {"severity": "error", "rule": "XSD", "message": message, "path": path}

    def _mark_provisional(self, report: ConstraintReport, path: str, detail: str = "valeur provisoire") -> None:
        report.provisional_fields.append(f"{path} ({detail})")

    def _constrain_element(
        self,
        element: XmlElement,
        declaration: XmlElement,
        path: str,
        report: ConstraintReport,
        depth: int,
    ) -> None:
        if depth > 80:
            report.violations.append(self._violation(path, "Profondeur de modele XSD recursive non prise en charge."))
            return
        attributes = {attribute.name: attribute for attribute in self._attributes_for(declaration)}
        for raw_name, value in list(element.attrib.items()):
            qname = etree.QName(raw_name)
            name = (qname.namespace, qname.localname)
            if qname.namespace == _XSI_NS:
                continue
            attribute = attributes.get(name)
            attribute_path = f"{path}/@{qname.localname}"
            if attribute is None:
                del element.attrib[raw_name]
                report.violations.append(
                    self._violation(attribute_path, f"Attribut interdit sur <{_local_name(element)}>; il a ete retire.")
                )
                continue
            if not self._value_is_valid(attribute.type_name, attribute.inline_type, value):
                replacement = self.provisional_value(
                    attribute.type_name,
                    attribute.inline_type,
                    fixed=attribute.fixed,
                    default=attribute.default,
                )
                if replacement is None:
                    del element.attrib[raw_name]
                    report.violations.append(
                        self._violation(attribute_path, "La valeur source ne respecte pas le XSD et aucune valeur provisoire valide n'a ete trouvee.")
                    )
                else:
                    element.set(raw_name, replacement)
                    self._mark_provisional(report, attribute_path)
                    report.violations.append(
                        self._violation(attribute_path, f"Valeur source non conforme au XSD; remplacee provisoirement par {replacement!r}.")
                    )
        for name, attribute in attributes.items():
            raw_name = _xml_qname(name)
            if attribute.required and raw_name not in element.attrib:
                value = self.provisional_value(
                    attribute.type_name,
                    attribute.inline_type,
                    fixed=attribute.fixed,
                    default=attribute.default,
                )
                if value is None:
                    report.violations.append(
                        self._violation(f"{path}/@{name[1]}", "Attribut obligatoire absent et aucune valeur provisoire acceptee par le XSD n'a ete trouvee.")
                    )
                else:
                    element.set(raw_name, value)
                    self._mark_provisional(report, f"{path}/@{name[1]}")

        value_type, inline_value_type = self._simple_value_type(declaration)
        if value_type is not None or inline_value_type is not None:
            value = element.text or ""
            if not value or not self._value_is_valid(value_type, inline_value_type, value):
                replacement = self.provisional_value(value_type, inline_value_type)
                if replacement is not None:
                    element.text = replacement
                    self._mark_provisional(report, f"{path}/text()")
                    if value:
                        report.violations.append(
                            self._violation(path, f"Valeur textuelle non conforme au XSD; remplacee provisoirement par {replacement!r}.")
                        )
                elif value:
                    element.text = None
                    report.violations.append(
                        self._violation(path, "La valeur textuelle ne respecte pas le XSD et aucune valeur provisoire valide n'a ete trouvee.")
                    )
                else:
                    self._mark_provisional(report, f"{path}/text()")
                    report.violations.append(
                        self._violation(path, "Valeur textuelle obligatoire absente et aucune valeur provisoire acceptee par le XSD n'a ete trouvee.")
                    )

        particle = self._particle_for(declaration)
        comments = [child for child in element if not isinstance(child.tag, str)]
        children = tuple(child for child in element if isinstance(child.tag, str))
        if particle is None:
            best = _Match((), (), 0, 0)
            remaining = children
        else:
            matches = self._match_particle(particle, children, {})
            best = max(matches, key=lambda match: (match.matched, -match.generated)) if matches else _Match((), children, 0, 0)
            remaining = best.remaining
        for dropped in remaining:
            child_name = etree.QName(dropped).localname
            child_path = f"{path}/{child_name}"
            allowed = self._particle_names(particle) if particle is not None else set()
            if _element_qname(dropped) not in allowed:
                message = f"L'element <{child_name}> n'est pas autorise sous <{_local_name(element)}> pour Issue {self.issue} / {self.dm_type}; contenu source non emis."
            else:
                message = f"L'element <{child_name}> depasse la cardinalite ou l'alternative autorisee sous <{_local_name(element)}>; contenu source non emis."
            preview = " ".join("".join(dropped.itertext()).split())[:120]
            if preview:
                message += f" Extrait non represente: {preview!r}."
            report.violations.append(self._violation(child_path, message))

        for child in list(element):
            element.remove(child)
        for item in best.items:
            element.append(item.element)
        for comment in comments:
            element.append(comment)
        for index, item in enumerate(best.items, start=1):
            child_name = etree.QName(item.element).localname
            child_path = f"{path}/{child_name}"
            if item.synthetic:
                self._mark_provisional(report, child_path, "structure provisoire imposee par le XSD")
            child_declaration = (
                item.declaration
                if item.declaration is not None
                else self.elements.get(_element_qname(item.element))
            )
            if child_declaration is not None:
                self._constrain_element(item.element, child_declaration, child_path, report, depth + 1)

    def _particle_names(self, particle: Particle | None) -> set[QName]:
        if particle is None:
            return set()
        names = {particle.name} if particle.kind == "element" and particle.name else set()
        for child in particle.children:
            names.update(self._particle_names(child))
        return names

    def _match_once(
        self,
        particle: Particle,
        candidates: tuple[XmlElement, ...],
        cache: MatchCache,
    ) -> list[_Match]:
        if particle.kind == "element":
            for index, candidate in enumerate(candidates):
                if _element_qname(candidate) == particle.name:
                    remaining = candidates[:index] + candidates[index + 1:]
                    return [_Match((_MatchItem(candidate, False, particle.declaration),), remaining, 1, 0)]
            if particle.name is None:
                return [_Match((), candidates, 0, 0)]
            generated = etree.Element(_xml_qname(particle.name))
            return [_Match((_MatchItem(generated, True, particle.declaration),), candidates, 0, 1)]
        if particle.kind in {"sequence", "all"}:
            states = [_Match((), candidates, 0, 0)]
            for child_particle in particle.children:
                next_states: list[_Match] = []
                for state in states:
                    for child_match in self._match_particle(child_particle, state.remaining, cache):
                        next_states.append(_Match(
                            state.items + child_match.items,
                            child_match.remaining,
                            state.matched + child_match.matched,
                            state.generated + child_match.generated,
                        ))
                states = self._prune_matches(next_states)
            return states
        if particle.kind == "choice":
            results: list[_Match] = []
            for child_particle in particle.children:
                results.extend(self._match_particle(child_particle, candidates, cache))
            return self._prune_matches(results)
        if particle.kind == "group" and particle.children:
            return self._match_particle(particle.children[0], candidates, cache)
        if particle.kind == "any" and candidates:
            candidate = candidates[0]
            return [_Match((_MatchItem(candidate, False, self.elements.get(_element_qname(candidate))),), candidates[1:], 1, 0)]
        return [_Match((), candidates, 0, 0)]

    def _match_particle(
        self,
        particle: Particle,
        candidates: tuple[XmlElement, ...],
        cache: MatchCache,
    ) -> list[_Match]:
        key = (id(particle), tuple(id(candidate) for candidate in candidates))
        cached = cache.get(key)
        if cached is not None:
            return cached
        matches = self._match_particle_uncached(particle, candidates, cache)
        cache[key] = matches
        return matches

    def _match_particle_uncached(
        self,
        particle: Particle,
        candidates: tuple[XmlElement, ...],
        cache: MatchCache,
    ) -> list[_Match]:
        if particle.kind == "choice" and particle.max_occurs is None:
            return self._match_repeating_choice(particle, candidates, cache)
        candidate_limit = len(candidates) + particle.min_occurs + 1
        upper = candidate_limit if particle.max_occurs is None else min(particle.max_occurs, candidate_limit)
        upper = max(upper, particle.min_occurs)
        states = [_Match((), candidates, 0, 0)]
        results: list[_Match] = []
        for occurrence in range(upper + 1):
            if occurrence >= particle.min_occurs:
                results.extend(states)
            if occurrence == upper:
                break
            next_states: list[_Match] = []
            for state in states:
                for unit in self._match_once(particle, state.remaining, cache):
                    next_states.append(_Match(
                        state.items + unit.items,
                        unit.remaining,
                        state.matched + unit.matched,
                        state.generated + unit.generated,
                    ))
            states = self._prune_matches(next_states)
            if not states:
                break
        return self._prune_matches(results)

    def _match_repeating_choice(
        self,
        particle: Particle,
        candidates: tuple[XmlElement, ...],
        cache: MatchCache,
    ) -> list[_Match]:
        # Les choix XSD compilés sont non ambigus : la première branche qui
        # consomme un enfant source évite d'enumerer toutes les partitions.
        upper = len(candidates) + particle.min_occurs + 1
        state = _Match((), candidates, 0, 0)
        results = [state] if particle.min_occurs == 0 else []

        for occurrence in range(upper):
            matches: list[tuple[tuple[int, int, int], _Match]] = []
            empty_matches: list[tuple[int, _Match]] = []
            for child_particle in particle.children:
                for match in self._match_particle(child_particle, state.remaining, cache):
                    if match.matched:
                        first = self._first_consumed_index(state.remaining, match.remaining)
                        matches.append(((first, -match.matched, match.generated), match))
                    else:
                        empty_matches.append((match.generated, match))

            if matches:
                unit = min(matches, key=lambda option: option[0])[1]
            elif occurrence < particle.min_occurs:
                unit = min(empty_matches, key=lambda option: option[0])[1] if empty_matches else _Match(
                    (), state.remaining, 0, 0,
                )
            else:
                break

            state = _Match(
                state.items + unit.items,
                unit.remaining,
                state.matched + unit.matched,
                state.generated + unit.generated,
            )
            completed = occurrence + 1
            if completed >= particle.min_occurs:
                results.append(state)
            if unit.matched == 0 and completed >= particle.min_occurs:
                break

        return self._prune_matches(results)

    @staticmethod
    def _first_consumed_index(
        candidates: tuple[XmlElement, ...],
        remaining: tuple[XmlElement, ...],
    ) -> int:
        remaining_ids = {id(candidate) for candidate in remaining}
        return next(
            (index for index, candidate in enumerate(candidates) if id(candidate) not in remaining_ids),
            len(candidates),
        )

    def _prune_matches(self, matches: list[_Match]) -> list[_Match]:
        best_by_remaining: dict[tuple[int, ...], _Match] = {}
        for match in matches:
            key = tuple(id(element) for element in match.remaining)
            current = best_by_remaining.get(key)
            if current is None or (match.matched, -match.generated) > (current.matched, -current.generated):
                best_by_remaining[key] = match
        return list(best_by_remaining.values())


@lru_cache(maxsize=6)
def load_xsd_model(issue: str, dm_type: str) -> XsdModel:
    stem = _SCHEMA_STEMS.get((dm_type or "").lower())
    if issue not in {"4.1", "4.2"} or stem is None:
        raise ValueError(f"Aucun modele XSD de generation pour Issue {issue} / type {dm_type}.")
    path = _SCHEMA_ROOT / f"issue-{issue}" / f"{stem}.xsd"
    if not path.is_file():
        raise ValueError(f"Schema XSD absent pour Issue {issue} / type {dm_type}.")
    return XsdModel(issue, dm_type, path)