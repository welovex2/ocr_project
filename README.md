# Benchline · 시험 데이터 워크스페이스

이미지별 시험 그래프를 OCR로 읽고, 시험원이 원본과 대조해 확정한 결과로 교육용 DOCX/PDF 보고서를 만드는 Streamlit 프로토타입입니다. Citymapper의 밝은 그린 포인트, 경로 안내 및 정류장 메타포, 친근하고 직관적인 카드 구성을 참고했습니다.

## 실행

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

첫 이미지 판독 시 RapidOCR의 로컬 모델이 준비될 수 있습니다. 이미지와 확정 결과는 원격 OCR 서비스로 전송하지 않습니다. 앱은 승인한 결과와 원본 이미지를 `records/`에 JSON 및 이미지 파일로 저장합니다.

## Streamlit Community Cloud 배포

Community Cloud는 GitHub 저장소의 파일을 복사해 앱을 실행합니다. 다음 파일을 저장소에 포함해야 합니다.

- `app.py`, `measurement.py`, `reporting.py`
- `requirements.txt`와 한글 PDF 글꼴 설치용 `packages.txt`
- 앱에서 사용하는 `doc/report_template.docx`
- 배포에서 샘플 갤러리를 보여주려면 합성 샘플 이미지 `img/`

1. 현재 소스 저장소는 [welovex2/ocr_project](https://github.com/welovex2/ocr_project)의 `main` 브랜치입니다. 이 저장소는 공개이므로 실제 고객·시험 이미지, 확정 결과, 김정미 보고서, 비밀번호나 API 키를 올리지 마세요. 프로젝트의 `.gitignore`는 `records/`, `rep/`, `.streamlit/secrets.toml`을 제외합니다.
2. [Streamlit Community Cloud](https://share.streamlit.io/)에 GitHub 계정으로 로그인하고 **Create app**을 누릅니다.
3. 저장소와 브랜치를 선택하고 **Main file path**에 `app.py`를 지정합니다. Python 버전 선택이 표시되면 개발 환경과 같은 **Python 3.12**를 선택한 뒤 배포합니다. Cloud가 `requirements.txt`와 `packages.txt`에서 필요한 패키지 및 한글 글꼴을 설치합니다.
4. 첫 OCR 실행에서는 모델 준비로 시간이 더 걸릴 수 있습니다. 배포 화면의 앱 주소를 열어 샘플 이미지와 보고서 생성을 확인합니다.

Cloud 앱 설정의 저장소/브랜치가 위 저장소의 `main`이고 메인 파일이 `app.py`라면, `main`에 push할 때 Streamlit Cloud가 자동으로 새 버전을 빌드·배포합니다. 빌드가 끝난 뒤 앱을 새로고침해 변경을 확인하세요. Cloud 앱이 다른 저장소나 브랜치를 가리키면 push만으로는 해당 사이트가 바뀌지 않으므로 Cloud 대시보드에서 연결 정보를 확인해야 합니다.

**시험 데이터 주의:** Community Cloud의 앱과 파일 시스템은 실제 시험기록을 보관하는 시스템으로 설계되지 않았습니다. `records/`에 저장한 결과는 인스턴스 재시작·재배포 시 사라질 수 있고, 다중 사용자용 영구 데이터베이스도 아닙니다. 실제 시험/고객 데이터를 다루기 전에는 회사의 보안 승인을 받고, 접근 통제·영구 저장소·백업이 보장된 사내 배포 환경을 사용하세요. 공개 링크에는 합성 샘플만 사용하세요.

## 사용 흐름

1. **검토 / 확정**에서 `img/`의 샘플을 선택하거나 PNG/JPG/WEBP 시험 이미지를 업로드합니다.
2. 그래프와 OCR이 읽은 마커 주파수·전력·보정계수를 대조하고, 필요한 값만 수정합니다.
3. 시험원/검토자 정보를 입력하고 확인 상자를 체크해 결과를 확정합니다. 중복 확정은 차단됩니다.
4. **실측 검증**에서 실제 이미지마다 장비 기록의 정답 주파수·전력·승인 판정을 입력하고 OCR 결과와 비교합니다. 검증 전에 정한 오차 허용 범위에 따라 일치율을 계산하고 DOCX 부록을 내려받을 수 있습니다. 사례는 브라우저 세션에만 보관되므로 창을 닫기 전에 부록을 저장하세요.
5. **확정 결과 · 성적서**에서 생성 단계와 진행률을 확인하며 DOCX/PDF를 만듭니다. 한 건이면 DOCX/PDF를 직접 다운로드할 수 있으며, 여러 건은 ZIP으로 내려받습니다.

보고서 PDF 용지 크기는 Word 템플릿 설정과 일치합니다. 한 건의 DOCX를 직접 받거나, 여러 건 ZIP은 먼저 압축 해제한 뒤 `.docx` 파일을 엽니다.

샘플 이미지 한 장은 독립적인 시험 결과 한 건으로 처리합니다. 판정 한계값과 CF 계산은 제공된 템플릿의 교육용 FCC Class B 가정을 따릅니다. 제공된 샘플과 템플릿은 합성 데이터이며, 이 앱에서 만든 결과물은 공식 시험성적서로 사용할 수 없습니다.

실측 검증은 사용자가 입력한 참조값을 정답으로 삼고, OCR 누락은 불일치로 계산합니다. PASS/FAIL 일치 결과 또한 앱의 교육용 기준 및 입력된 CF에 대한 비교이므로, 승인된 시험 규격과 별도로 검증하기 전에는 공식 판정 정확도로 해석하면 안 됩니다. 기준 데이터와 이미지가 보고서 부록에 포함될 수 있으니 승인된 보안 환경에서만 사용하세요.

## 테스트

```powershell
python -m unittest discover -s tests -v
```
