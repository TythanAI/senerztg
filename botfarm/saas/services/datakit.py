"""Data Toolkit — convert between CSV, JSON, XML and YAML; validate and flatten."""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from saascore.app import ServiceSpec

MAX_INPUT = 2_000_000
FORMATS = ("csv", "json", "xml", "yaml", "tsv")


class ConvertRequest(BaseModel):
    data: str = Field(..., max_length=MAX_INPUT)
    source: str = Field(..., description=f"One of: {', '.join(FORMATS)}")
    target: str = Field(..., description=f"One of: {', '.join(FORMATS)}")
    delimiter: str = Field(",", max_length=1)
    root: str = Field("root", description="XML root element name")


class FlattenRequest(BaseModel):
    data: str = Field(..., max_length=MAX_INPUT)
    separator: str = Field(".", max_length=3)


def _parse(data: str, source: str, delimiter: str) -> Any:
    source = source.lower()
    try:
        if source == "json":
            return json.loads(data)
        if source == "yaml":
            return yaml.safe_load(data)
        if source in {"csv", "tsv"}:
            sep = "\t" if source == "tsv" else (delimiter or ",")
            reader = csv.DictReader(io.StringIO(data), delimiter=sep)
            rows = [dict(row) for row in reader]
            if not rows:
                raise HTTPException(400, "No data rows found — is the header line present?")
            return rows
        if source == "xml":
            return _xml_to_dict(ET.fromstring(data))
    except HTTPException:
        raise
    except (json.JSONDecodeError, yaml.YAMLError, ET.ParseError, csv.Error) as exc:
        raise HTTPException(400, f"Could not parse {source}: {exc}") from exc

    raise HTTPException(400, f"source must be one of: {', '.join(FORMATS)}")


def _serialise(value: Any, target: str, delimiter: str, root: str) -> tuple[str, str]:
    target = target.lower()
    if target == "json":
        return json.dumps(value, ensure_ascii=False, indent=2, default=str), "application/json"
    if target == "yaml":
        return yaml.safe_dump(value, allow_unicode=True, sort_keys=False), "text/yaml"
    if target in {"csv", "tsv"}:
        rows = value if isinstance(value, list) else [value]
        if not rows or not all(isinstance(r, dict) for r in rows):
            raise HTTPException(
                400, "CSV output needs a list of flat objects — try flattening first"
            )
        # Union of keys, first-seen order: rows with missing fields stay aligned.
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer, fieldnames=fields, delimiter="\t" if target == "tsv" else (delimiter or ",")
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _scalar(row.get(k)) for k in fields})
        return buffer.getvalue(), "text/csv"
    if target == "xml":
        element = ET.Element(root)
        _dict_to_xml(value, element)
        return ET.tostring(element, encoding="unicode"), "application/xml"

    raise HTTPException(400, f"target must be one of: {', '.join(FORMATS)}")


def _scalar(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _xml_to_dict(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return element.text or ""
    result: dict[str, Any] = {}
    for child in children:
        value = _xml_to_dict(child)
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(value)
        else:
            result[child.tag] = value
    return result


def _dict_to_xml(value: Any, parent: ET.Element) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            tag = str(key).replace(" ", "_") or "field"
            if not tag[0].isalpha() and tag[0] != "_":
                tag = f"_{tag}"
            child = ET.SubElement(parent, tag)
            _dict_to_xml(item, child)
    elif isinstance(value, list):
        for item in value:
            child = ET.SubElement(parent, "item")
            _dict_to_xml(item, child)
    else:
        parent.text = "" if value is None else str(value)


def _flatten(value: Any, separator: str, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            out.update(_flatten(item, separator, f"{prefix}{separator}{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out.update(_flatten(item, separator, f"{prefix}[{index}]"))
    else:
        out[prefix or "value"] = value
    return out


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/data/convert", response_class=PlainTextResponse)
    async def convert(request: Request, body: ConvertRequest):
        """Convert between CSV, TSV, JSON, XML and YAML."""
        await request.app.state.require_key(request)
        parsed = _parse(body.data, body.source, body.delimiter)
        text, mime = _serialise(parsed, body.target, body.delimiter, body.root)
        return PlainTextResponse(text, media_type=mime)

    @router.post("/data/flatten")
    async def flatten(request: Request, body: FlattenRequest) -> dict:
        """Flatten nested JSON/YAML into dotted keys — ready for a spreadsheet."""
        await request.app.state.require_key(request)
        try:
            parsed = json.loads(body.data)
        except json.JSONDecodeError:
            try:
                parsed = yaml.safe_load(body.data)
            except yaml.YAMLError as exc:
                raise HTTPException(400, f"Input is neither JSON nor YAML: {exc}") from exc

        flat = _flatten(parsed, body.separator)
        return {"keys": len(flat), "flat": flat}

    @router.post("/data/validate")
    async def validate(request: Request, body: FlattenRequest) -> dict:
        """Check whether the input is well-formed, and report its shape."""
        await request.app.state.require_key(request)
        report: dict[str, Any] = {}

        for name, parser in (
            ("json", json.loads),
            ("yaml", yaml.safe_load),
            ("xml", ET.fromstring),
        ):
            try:
                parsed = parser(body.data)
                report[name] = {"valid": True, "type": type(parsed).__name__}
                if name != "xml" and isinstance(parsed, (dict, list)):
                    report[name]["items"] = len(parsed)
                    report[name]["depth"] = _depth(parsed)
            except Exception as exc:
                report[name] = {"valid": False, "error": str(exc)[:200]}

        return {"bytes": len(body.data), "formats": report}

    return router


def _depth(value: Any, level: int = 1) -> int:
    if isinstance(value, dict) and value:
        return max(_depth(v, level + 1) for v in value.values())
    if isinstance(value, list) and value:
        return max(_depth(v, level + 1) for v in value)
    return level


def spec() -> ServiceSpec:
    return ServiceSpec(
        name="datakit",
        title="Data Toolkit API",
        tagline="CSV ⇄ JSON ⇄ XML ⇄ YAML, plus flattening and validation.",
        summary="Convert tabular and tree data between formats, flatten nested structures, validate syntax.",
        router=build_router(),
        endpoints=[
            ("POST /v1/data/convert", "Convert between csv/tsv/json/xml/yaml"),
            ("POST /v1/data/flatten", "Nested structure → dotted keys"),
            ("POST /v1/data/validate", "Well-formedness and shape report"),
        ],
        example=(
            'curl -X POST https://api.example.com/v1/data/convert \\\n'
            '  -H "Authorization: Bearer sk_live_..." \\\n'
            '  -d \'{"data":"a,b\\n1,2","source":"csv","target":"json"}\''
        ),
    )
