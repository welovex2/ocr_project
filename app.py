from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance

from measurement import MarkerReading, calculate_measurement, parse_marker_text
from reporting import build_docx_report, build_pdf_report, safe_filename
from validation import validate_confirmed_record


ROOT = Path(__file__).resolve().parent
SAMPLE_DIR = ROOT / "img"
TEMPLATE_PATH = ROOT / "doc" / "report_template.docx"
RECORD_DIR = ROOT / "records"
IMAGE_DIR = RECORD_DIR / "images"

st.set_page_config(
    page_title="Benchline | 시험 데이터 워크스페이스",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');
    :root { --ink:#13283d; --navy:#123c5a; --blue:#2678a8; --green:#00a878;
            --lime:#c8f169; --paper:#f5f7f3; --line:#dce5dc; --muted:#617269; }
    html, body, [class*="css"] { font-family:'DM Sans','Noto Sans KR',sans-serif; }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stSidebar"] { background:#123c5a; }
    [data-testid="stSidebar"] * { color:#f4faef; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * { color:#14213d; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label { padding:5px 0; font-weight:600; }
    .block-container { padding-top:1.35rem; padding-bottom:2.5rem; max-width:1420px; }
    .hero { border-radius:24px; padding:25px 30px; color:#fff;
            background:linear-gradient(112deg,#123c5a 0%,#175477 61%,#008c67 120%);
            margin-bottom:17px; box-shadow:0 12px 32px rgba(18,60,90,.13); }
    .hero h1 { margin:2px 0 6px; font-size:31px; letter-spacing:-.8px; color:#fff; }
    .hero p { margin:0; color:#d7eee3; font-size:14px; }
    .eyebrow { text-transform:uppercase; letter-spacing:1.6px; font-size:10px;
               font-weight:800; color:var(--lime); }
    .metric-card { background:#fff; border:1px solid var(--line); border-radius:18px;
                   padding:17px 19px; min-height:95px; box-shadow:0 4px 16px #163c4d0a; }
    .metric-label { color:var(--muted); font-size:12px; }
    .metric-value { color:var(--ink); font-size:26px; font-weight:800; margin-top:5px; }
    .section-title { font-weight:800; font-size:18px; color:var(--ink); margin:2px 0 7px; }
    .hint { color:var(--muted); font-size:12px; line-height:1.6; }
    .warning { background:#fff8df; border:1px solid #f1dc99; border-radius:14px;
               padding:12px 15px; color:#705819; font-size:12px; margin:9px 0 17px; }
    .route { display:flex; align-items:center; gap:0; margin:9px 0 19px;
             background:#fff; border:1px solid var(--line); border-radius:17px;
             padding:13px 20px; box-shadow:0 4px 16px #163c4d08; }
    .route-stop { display:flex; align-items:center; gap:9px; color:#617269;
                  font-size:12px; font-weight:700; white-space:nowrap; }
    .route-dot { width:27px; height:27px; display:grid; place-items:center; border-radius:50%;
                 background:#edf2eb; color:#708078; font-size:12px; font-weight:800; }
    .route-stop.done { color:#00845d; }
    .route-stop.done .route-dot { background:#d8f6e8; color:#00845d; }
    .route-stop.active { color:#123c5a; }
    .route-stop.active .route-dot { background:#c8f169; color:#123c5a; }
    .route-line { height:3px; flex:1; min-width:20px; margin:0 10px;
                  border-radius:4px; background:#dfe8df; }
    .route-line.done { background:#00a878; }
    .welcome-card { background:#fff; border:1px solid var(--line); border-radius:19px;
                    padding:19px 21px; height:100%; }
    .welcome-icon { font-size:23px; }
    .welcome-title { font-weight:800; font-size:15px; margin:7px 0 4px; }
    .welcome-copy { color:var(--muted); font-size:12px; line-height:1.55; }
    .result-card { background:#fff; border:1px solid var(--line); border-radius:16px;
                   padding:13px 15px; margin:9px 0 12px; }
    .stButton button[kind="primary"] { background:#008c66; border-color:#008c66;
                                       font-weight:700; min-height:44px; }
    .stButton button { border-radius:12px; }
    [data-testid="stSelectbox"] label { font-weight:800; color:#123c5a; }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background:#fff !important; border:2px solid #00a878 !important;
        border-radius:13px !important; min-height:52px;
        box-shadow:0 3px 12px rgba(0,168,120,.10);
    }
    [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
        box-shadow:0 0 0 4px rgba(0,168,120,.18) !important;
    }
    div[data-testid="stMetric"] { background:#fff; border:1px solid var(--line);
                                  padding:11px 14px; border-radius:14px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _ocr_marker(image_bytes: bytes) -> MarkerReading:
    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert("RGB")
        width, height = image.size
        crop = image.crop(
            (
                int(width * 0.59),
                int(height * 0.085),
                int(width * 0.84),
                int(height * 0.19),
            )
        )
        crop = ImageEnhance.Contrast(crop).enhance(1.4)
        crop = ImageEnhance.Sharpness(crop).enhance(1.6)
        crop = crop.resize((crop.width * 3, crop.height * 3))

    detections, _ = _ocr_engine()(np.asarray(crop))
    lines: list[tuple[str, float]] = []
    for detection in detections or []:
        if len(detection) >= 3:
            lines.append((str(detection[1]), float(detection[2])))
    return parse_marker_text(lines)


def _image_sources(uploads: list[Any]) -> list[dict[str, Any]]:
    sources = []
    if SAMPLE_DIR.is_dir():
        for path in sorted(SAMPLE_DIR.glob("*")):
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            sources.append(
                {
                    "id": f"sample-{path.name}",
                    "name": path.name,
                    "bytes": path.read_bytes(),
                    "source": "샘플",
                }
            )
    for upload in uploads:
        image_bytes = upload.getvalue()
        digest = hashlib.sha256(image_bytes).hexdigest()[:12]
        sources.append(
            {
                "id": f"upload-{digest}",
                "name": upload.name,
                "bytes": image_bytes,
                "source": "업로드",
            }
        )
    return sources


def _read_records() -> tuple[list[dict[str, Any]], list[str]]:
    if not RECORD_DIR.is_dir():
        return [], []
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted(RECORD_DIR.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or "result" not in record:
                raise ValueError("기록의 필수 필드가 없습니다.")
            records.append(record)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            errors.append(f"{path.name}: {error}")
    return records, errors


def _save_record(record: dict[str, Any], image_bytes: bytes) -> None:
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    image_path = IMAGE_DIR / f"{record['id']}{Path(record['source_name']).suffix.lower()}"
    record["image_file"] = str(image_path.relative_to(ROOT))
    json_path = RECORD_DIR / f"{record['id']}.json"
    image_path.write_bytes(image_bytes)
    try:
        json_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        image_path.unlink(missing_ok=True)
        raise


def _display_source(source: dict[str, Any]) -> str:
    return f"{source['name']} · {source['source']}"


def _hero(eyebrow: str, title: str, description: str) -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{eyebrow}</div>'
        f"<h1>{title}</h1><p>{description}</p></div>",
        unsafe_allow_html=True,
    )


def _route_steps(active: int) -> None:
    labels = ["이미지 선택", "값 확인", "결과 확정"]
    parts = ['<div class="route" aria-label="시험 진행 단계">']
    for index, label in enumerate(labels):
        state = "done" if index < active else "active" if index == active else ""
        parts.append(
            f'<div class="route-stop {state}"><span class="route-dot">'
            f'{"✓" if index < active else index + 1}</span><span>{label}</span></div>'
        )
        if index < len(labels) - 1:
            parts.append(
                f'<span class="route-line {"done" if index < active else ""}"></span>'
            )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _review_page(sources: list[dict[str, Any]]) -> None:
    _hero(
        "GRAPH CHECK · STEP 2 OF 3",
        "그래프 한 장씩, 정확하게 확인해요.",
        "읽힌 값은 먼저 채워 두었어요. 원본과 대조한 뒤, 마지막 확인 버튼으로 안전하게 확정하세요.",
    )
    _route_steps(1)
    last_saved = st.session_state.get("last_saved_message")
    if last_saved:
        st.success(f"{last_saved} 결과를 확정해 저장했어요. 이 화면에서 다음 그래프도 계속 확인할 수 있습니다.")
    st.markdown(
        '<div class="warning"><b>교육용 샘플 데이터</b> — 이 앱과 제공된 이미지·템플릿은 '
        "합성 데이터입니다. 생성되는 보고서는 공식 시험성적서로 사용할 수 없습니다.</div>",
        unsafe_allow_html=True,
    )
    if not sources:
        st.info("왼쪽의 **이미지 추가**에서 시험 결과 그래프를 올리면 바로 검토할 수 있어요.")
        return

    saved_records, _ = _read_records()
    saved_hashes = {record.get("source_sha256") for record in saved_records}
    source_hashes = {
        source["id"]: hashlib.sha256(source["bytes"]).hexdigest()
        for source in sources
    }
    labels = {
        source["id"]: (
            f"{'✅ 확정 완료' if source_hashes[source['id']] in saved_hashes else '🟢 검토 대기'}"
            f"　{source['name']}　·　{source['source']}"
        )
        for source in sources
    }
    ids = list(labels)
    current_id = st.session_state.get("selected_source_id")
    if current_id not in ids:
        current_id = ids[0]
    pending_count = sum(source_hashes[source_id] not in saved_hashes for source_id in ids)
    with st.container(border=True):
        st.markdown("### 🗂️ 검토할 그래프를 선택하세요")
        st.caption(
            f"아래 초록색 선택 상자를 누르면 이미지 목록이 열립니다 · "
            f"검토 대기 {pending_count}장 / 전체 {len(ids)}장"
        )
        selected_id = st.selectbox(
            "👇 여기를 눌러 시험 이미지 목록 열기",
            ids,
            index=ids.index(current_id),
            format_func=lambda source_id: labels[source_id],
            help="목록에서 그래프 파일을 고르면 원본 이미지와 OCR 결과를 함께 확인할 수 있습니다.",
        )
    st.session_state["selected_source_id"] = selected_id
    source = next(item for item in sources if item["id"] == selected_id)

    cache = st.session_state.setdefault("ocr_results", {})
    if selected_id not in cache:
        try:
            with st.spinner("마커 값을 읽는 중…"):
                cache[selected_id] = _ocr_marker(source["bytes"])
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            cache[selected_id] = error

    source_hash = source_hashes[selected_id]
    already_saved = source_hash in saved_hashes
    left, right = st.columns([1.08, 0.92], gap="large")
    with left:
        st.markdown('<div class="section-title">원본 그래프 <span style="color:#008c66">· 눈으로 대조해 주세요</span></div>', unsafe_allow_html=True)
        st.image(source["bytes"], width="stretch")
        reading = cache[selected_id]
        if isinstance(reading, MarkerReading):
            st.caption(
                f"이미지 판독 신뢰도 {reading.confidence:.0%} · "
                f"인식 텍스트: {reading.raw_text or '인식된 문자가 없습니다.'}"
            )
        elif isinstance(reading, Exception):
            st.warning(f"자동 판독을 완료하지 못했습니다: {reading}")

    with right:
        st.markdown('<div class="section-title">읽어온 값</div>', unsafe_allow_html=True)
        if isinstance(reading, MarkerReading):
            if reading.frequency_mhz is None or reading.power_uw is None:
                st.warning("주파수 또는 전력을 읽지 못했습니다. 이미지를 대조해 직접 입력해 주세요.")
            elif reading.confidence < 0.85:
                st.warning("OCR 신뢰도가 낮습니다. 원본 그래프와 값을 다시 대조해 주세요.")
        if already_saved:
            st.info("이 원본 이미지는 이미 확정되어 있습니다. 중복 확정을 막기 위해 다시 저장할 수 없습니다.")
        field_suffix = selected_id
        default_frequency = (
            reading.frequency_mhz
            if isinstance(reading, MarkerReading) and reading.frequency_mhz is not None
            else 0.0
        )
        default_power = (
            reading.power_uw
            if isinstance(reading, MarkerReading) and reading.power_uw is not None
            else 0.0
        )
        frequency_col, power_col = st.columns(2)
        frequency = frequency_col.number_input(
            "주파수 · MHz", min_value=0.0, value=float(default_frequency),
            step=0.001, format="%.3f", key=f"frequency-{field_suffix}",
        )
        power = power_col.number_input(
            "전력 · µW", min_value=0.0, value=float(default_power),
            step=0.01, format="%.2f", key=f"power-{field_suffix}",
        )
        with st.expander("보정계수 CF 설정 · 교육용 기본값 0.00 dB"):
            cf_db = st.number_input(
                "보정계수 · dB", value=0.0, step=0.1, format="%.2f",
                key=f"cf-{field_suffix}",
                help="실측 보정값이 아닌 교육용 가정값입니다.",
            )

        calculated: dict[str, Any] | None
        try:
            calculated = calculate_measurement(frequency, power, cf_db)
        except ValueError as error:
            calculated = None
            st.info(str(error))

        if calculated:
            verdict = calculated["verdict"]
            verdict_color = "#00845d" if verdict == "PASS" else "#b74138"
            st.markdown(
                f'<div class="result-card"><div class="hint">자동 계산 결과</div>'
                f'<b style="font-size:20px;color:{verdict_color}">{verdict}</b>'
                f'<span style="color:#617269">　마진 {calculated["margin"]:.2f} dB'
                f'　·　한계 {calculated["limit"]:.1f} dBµV/m</span></div>',
                unsafe_allow_html=True,
            )

        first = source["name"].rsplit(".", 1)[0]
        with st.form(f"confirm-{field_suffix}", clear_on_submit=False):
            st.markdown('<div class="section-title">확정 담당자</div>', unsafe_allow_html=True)
            tester_col, reviewer_col = st.columns(2)
            tester = tester_col.text_input("시험원 *", key=f"tester-{field_suffix}")
            reviewer = reviewer_col.text_input("검토자 *", key=f"reviewer-{field_suffix}")
            with st.expander("성적서 정보 더 보기 · 시료 / 규격 / 특이사항"):
                doc_col, date_col = st.columns(2)
                doc_no = doc_col.text_input(
                    "문서번호 *", value=f"RE-{date.today():%Y%m%d}-{first[-2:]}",
                    key=f"doc-{field_suffix}",
                )
                test_date = date_col.date_input("시험일", value=date.today(), key=f"date-{field_suffix}")
                test_name = st.text_input("시험명", value="방사성 방출 (RE)", key=f"name-{field_suffix}")
                sample_name = st.text_input(
                    "시료명", value="교육용 합성 데이터", key=f"sample-{field_suffix}"
                )
                standard = st.text_input(
                    "적용 규격", value="FCC Part 15 Subpart B Class B (교육용)",
                    key=f"standard-{field_suffix}",
                )
                remarks = st.text_area(
                    "특이사항", value=f"원본 이미지: {source['name']} · 교육용 합성 데이터",
                    key=f"remarks-{field_suffix}",
                )
            checked = st.checkbox(
                "그래프와 입력값을 대조하고 판정을 확인했습니다.",
                key=f"checked-{field_suffix}",
            )
            submitted = st.form_submit_button(
                "✓  확인 완료 · 결과 확정",
                type="primary",
                width="stretch",
                disabled=calculated is None or already_saved,
            )

        if submitted:
            if not checked:
                st.error("확정할 수 없습니다. 먼저 그래프와 값을 대조하고 확인란을 체크해 주세요.")
            elif not doc_no.strip() or not tester.strip() or not reviewer.strip():
                st.error("확정할 수 없습니다. 문서번호, 시험원, 검토자는 필수 입력입니다.")
            elif calculated is None:
                st.error("측정값이 유효하지 않아 확정할 수 없습니다.")
            else:
                record = {
                    "id": uuid4().hex,
                    "source_name": source["name"],
                    "source_sha256": source_hash,
                    "doc_no": doc_no.strip(),
                    "test_date": test_date.isoformat(),
                    "test_name": test_name.strip(),
                    "tester": tester.strip(),
                    "reviewer": reviewer.strip(),
                    "sample_name": sample_name.strip(),
                    "standard": standard.strip(),
                    "cf_db": cf_db,
                    "frequency_mhz": frequency,
                    "power_uw": power,
                    "ocr_confidence": reading.confidence if isinstance(reading, MarkerReading) else 0.0,
                    "result": calculated,
                    "remarks": remarks.strip(),
                    "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "confirmed": True,
                }
                try:
                    _save_record(record, source["bytes"])
                except OSError as error:
                    st.error(f"확정 데이터를 저장하지 못했습니다: {error}")
                else:
                    st.session_state["last_saved_message"] = source["name"]
                    st.rerun()


def _records_page(records: list[dict[str, Any]]) -> None:
    _hero(
        "REPORT STUDIO · STEP 3 OF 3",
        "확정된 결과를 성적서로 만들어요.",
        "필요한 건을 고른 다음 DOCX와 같은 세로 페이지의 PDF로 내보내세요.",
    )
    _route_steps(2)
    if not records:
        st.info("아직 확정된 결과가 없어요. 그래프 검토 메뉴에서 첫 결과를 확인해 주세요.")
        return

    st.dataframe(
        [
            {
                "시험 ID": record["id"][:8],
                "문서번호": record["doc_no"],
                "시험일": record["test_date"],
                "이미지": record["source_name"],
                "주파수 (MHz)": f"{float(record['frequency_mhz']):.3f}",
                "전력 (µW)": f"{float(record['power_uw']):.2f}",
                "마진 (dB)": f"{float(record['result']['margin']):.2f}",
                "판정": record["result"]["verdict"],
                "검토자": record["reviewer"],
            }
            for record in records
        ],
        hide_index=True,
        width="stretch",
    )
    record_map = {record["id"]: record for record in records}
    selected_ids = st.multiselect(
        "성적서를 만들 확정 시험 선택",
        list(record_map),
        format_func=lambda record_id: (
            f"{record_map[record_id]['test_date']} · "
            f"{record_map[record_id]['doc_no']} · "
            f"{record_map[record_id]['source_name']} · "
            f"{record_map[record_id]['result']['verdict']} · "
            f"{record_id[:8]}"
        ),
    )
    st.caption(
        f"선택됨: **{len(selected_ids)}건** · "
        "Word 파일을 바로 받거나, 여러 건은 ZIP으로 한 번에 받을 수 있습니다."
    )
    selection_key = tuple(sorted(selected_ids))
    generated = st.session_state.get("generated_reports")
    if generated and generated.get("selection") != selection_key:
        generated = None
        st.session_state.pop("generated_reports", None)

    if st.button(
        f"선택한 {len(selected_ids)}건 · 성적서 생성 시작",
        type="primary",
        width="stretch",
        disabled=not selected_ids,
    ):
        try:
            for record_id in selected_ids:
                validate_confirmed_record(record_map[record_id])
            with st.status("보고서 생성 준비 중…", expanded=True) as status:
                template = TEMPLATE_PATH.read_bytes()
                package = io.BytesIO()
                individual: dict[str, dict[str, bytes]] = {}
                total_steps = len(selected_ids) * 2
                progress = st.progress(0, text="템플릿과 페이지 크기를 확인하고 있어요.")
                completed = 0
                with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
                    for record_id in selected_ids:
                        record = record_map[record_id]
                        stem = (
                            f"{safe_filename(record['doc_no'])}_"
                            f"{safe_filename(record['source_name'])}_"
                            f"{record['id'][:8]}"
                        )
                        status.update(
                            label=f"{record['source_name']} · Word 문서 만드는 중",
                            state="running",
                        )
                        docx_bytes = build_docx_report(template, record)
                        docx_name = f"{stem}.docx"
                        archive.writestr(docx_name, docx_bytes)
                        completed += 1
                        progress.progress(
                            completed / total_steps,
                            text=f"{completed}/{total_steps} 단계 · Word 문서 완료",
                        )

                        status.update(
                            label=f"{record['source_name']} · PDF 만드는 중",
                            state="running",
                        )
                        pdf_bytes = build_pdf_report(record, template)
                        pdf_name = f"{stem}.pdf"
                        archive.writestr(pdf_name, pdf_bytes)
                        completed += 1
                        progress.progress(
                            completed / total_steps,
                            text=f"{completed}/{total_steps} 단계 · PDF 완료",
                        )
                        individual[record_id] = {
                            "docx_name": docx_name,
                            "docx": docx_bytes,
                            "pdf_name": pdf_name,
                            "pdf": pdf_bytes,
                        }
                st.session_state["generated_reports"] = {
                    "selection": selection_key,
                    "package": package.getvalue(),
                    "individual": individual,
                }
                generated = st.session_state["generated_reports"]
                status.update(
                    label=f"완료! {len(selected_ids)}건의 DOCX/PDF를 모두 만들었습니다.",
                    state="complete",
                )
        except (OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile) as error:
            st.error(f"성적서 생성에 실패했습니다. 파일을 저장하지 않았습니다: {error}")
            generated = None

    if generated and generated.get("selection") == selection_key:
        st.success(
            f"생성 완료 · {len(generated['individual'])}건, "
            f"DOCX {len(generated['individual'])}개 + PDF {len(generated['individual'])}개"
        )
        if len(selected_ids) == 1:
            files = generated["individual"][selected_ids[0]]
            docx_col, pdf_col, zip_col = st.columns(3)
            docx_col.download_button(
                "Word 문서 (.docx)",
                data=files["docx"],
                file_name=files["docx_name"],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                width="stretch",
                type="primary",
            )
            pdf_col.download_button(
                "PDF 문서",
                data=files["pdf"],
                file_name=files["pdf_name"],
                mime="application/pdf",
                width="stretch",
            )
            zip_col.download_button(
                "ZIP으로 함께 받기",
                data=generated["package"],
                file_name="confirmed_test_reports.zip",
                mime="application/zip",
                width="stretch",
            )
        else:
            st.download_button(
                "DOCX + PDF ZIP 다운로드",
                data=generated["package"],
                file_name="confirmed_test_reports.zip",
                mime="application/zip",
                type="primary",
                width="stretch",
            )
            st.caption("ZIP을 먼저 압축 해제한 뒤 원하는 .docx 또는 .pdf 파일을 열어 주세요.")

    csv_buffer = io.StringIO()
    columns = [
        "doc_no", "test_date", "source_name", "frequency_mhz", "power_uw",
        "cf_db", "dbm", "dbuv_m", "limit", "margin", "verdict", "tester", "reviewer",
    ]
    writer = csv.DictWriter(csv_buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                **record,
                **record["result"],
            }
        )
    st.download_button(
        "확정 결과 CSV 다운로드",
        data=csv_buffer.getvalue().encode("utf-8-sig"),
        file_name="confirmed_measurements.csv",
        mime="text/csv",
    )


def main() -> None:
    st.sidebar.markdown("## BENCHLINE")
    st.sidebar.caption("시험 그래프에서 성적서까지, 한 번에")
    page = st.sidebar.radio(
        "작업 메뉴",
        ["오늘의 작업", "그래프 검토", "확정 결과 · 성적서"],
        key="main_navigation",
        help=(
            "오늘의 작업: 이미지와 진행 현황\n"
            "그래프 검토: OCR 값을 확인하고 시험원이 확정\n"
            "확정 결과 · 성적서: DOCX, PDF, CSV 다운로드"
        ),
    )
    st.sidebar.caption(
        "**오늘의 작업** — 시험 진행 현황\n\n"
        "**그래프 검토** — 이미지와 OCR 값을 대조\n\n"
        "**확정 결과 · 성적서** — 승인 결과 출력"
    )
    uploads = st.sidebar.file_uploader(
        "이미지 추가",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        help="PNG/JPG/WEBP 시험 결과 그래프를 추가하세요. 승인 전에는 현재 브라우저 세션에서만 처리합니다.",
    )
    st.sidebar.caption("새 이미지를 올리면 **그래프 검토** 목록에 바로 나타납니다.")
    sources = _image_sources(uploads or [])
    records, record_errors = _read_records()
    for error in record_errors:
        st.error(f"저장 기록을 읽지 못했습니다: {error}")

    if page == "그래프 검토":
        _review_page(sources)
    elif page == "확정 결과 · 성적서":
        _records_page(records)
    else:
        _hero(
            "BENCHLINE · YOUR TEST-DAY ROUTE",
            "오늘도 정확하게.",
            "그래프 한 장에서 시작해, 시험원이 확인한 성적서까지 차근차근 이어집니다.",
        )
        _route_steps(0)
        st.markdown(
            '<div class="warning"><b>프로토타입 안내</b> — 제공된 이미지와 성적서 템플릿은 '
            "교육용 합성 데이터입니다. OCR 결과는 반드시 원본과 대조해야 하며 공식 시험성적서로 사용할 수 없습니다.</div>",
            unsafe_allow_html=True,
        )
        sample_count = sum(1 for source in sources if source["source"] == "샘플")
        metric_cols = st.columns(3)
        for column, label, value in zip(
            metric_cols,
            ("샘플 이미지", "업로드 이미지", "확정된 결과"),
            (
                sample_count,
                len(sources) - sample_count,
                len(records),
            ),
        ):
            column.markdown(
                f'<div class="metric-card"><div class="metric-label">{label}</div>'
                f'<div class="metric-value">{value}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">다음 정류장, 어디로 갈까요?</div>', unsafe_allow_html=True)
        st.caption("원하는 단계로 바로 이동할 수 있어요. 한 건씩 천천히 확인해도 괜찮습니다.")
        task_cols = st.columns(3)
        task_cards = [
            ("📡", "01 · 그래프 검토", "샘플 또는 업로드 이미지를 열고 OCR 값을 원본과 비교해요."),
            ("✅", "02 · 시험원 확정", "담당자와 확인 내용을 입력해야만 결과가 저장돼요."),
            ("🧾", "03 · 성적서 받기", "진행 상태를 보면서 DOCX와 PDF를 만들어요."),
        ]
        for column, (icon, title, copy) in zip(task_cols, task_cards):
            column.markdown(
                f'<div class="welcome-card"><div class="welcome-icon">{icon}</div>'
                f'<div class="welcome-title">{title}</div>'
                f'<div class="welcome-copy">{copy}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">샘플 그래프 미리보기</div>', unsafe_allow_html=True)
        st.caption("img 폴더의 이미지 한 장이 검토할 시험 결과 한 건입니다.")
        sample_sources = [source for source in sources if source["source"] == "샘플"]
        if sample_sources:
            columns = st.columns(4)
            for index, source in enumerate(sample_sources[:8]):
                with columns[index % 4]:
                    st.image(source["bytes"], caption=source["name"], width="stretch")
        else:
            st.info("img 폴더에 표시할 이미지가 없습니다. 왼쪽에서 결과 이미지를 업로드해 주세요.")
        if record_errors:
            st.warning("일부 저장 기록을 불러오지 못했습니다. 위 오류를 확인해 주세요.")


if __name__ == "__main__":
    main()
