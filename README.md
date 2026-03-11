# Aseprite Tag Master

Aseprite(`.ase`, `.aseprite`) 파일의 애니메이션 태그(Tags) 이름과 속성을 자동으로 검수하고 일괄 수정해주는 Windows 데스크톱 애플리케이션입니다.

## 주요 기능 (Features)
1. **드래그 앤 드롭 지원**: 여러 개의 Aseprite 파일을 한 번에 불러와 작업할 수 있습니다.
2. **자동 네이밍 규칙 적용**:
   - 모든 단어의 첫 글자를 대문자로 변환 (`expose_groggy` -> `Expose_Groggy`)
   - `_` 기준 단어 분리 및 띄어쓰기 없는 합성어(예: `powerwave`)를 자동으로 쪼개어 대문자 적용 (`PowerWave`)
3. **스마트 스펠링 교정**:
   - 내장된 '단어 사전'을 기준으로 태그 이름의 스펠링 오류를 자동 탐지 및 교정 (예: `Attck` -> `Attack`)
   - UI 내에서 단어 사전을 언제든 커스텀 및 편집 가능
4. **다중 일괄 단어 치환**: 
   - 특정 단어(예: `Break` -> `Groggy`)를 일괄적으로 찾아 바꾸는 기능을 다중 규칙으로 적용 가능
5. **안전한 검수 리포트**:
   - 파일 수정 전, 어떤 태그가 어떻게 바뀌고 어떤 규칙이 위반되었는지 표 형태로 미리보기 제공
   - 적용을 원치 않는 태그는 개별적으로 체크 해제 가능
6. **Aseprite 원본 보호**: 파일을 직접 뜯어고치지 않고 Aseprite 자체 Lua 엔진을 백그라운드로 호출하여 저장하므로 파일 손상 위험이 없습니다.

## 설치 및 실행 방법 (How to Run)

1. Python 3.9 이상 설치
2. 가상환경 세팅 및 라이브러리 설치
```bash
python -m venv venv
.\venv\Scripts\activate
pip install PyQt6 wordninja thefuzz python-Levenshtein
```
3. 프로그램 실행
```bash
python main.py
```
*(참고: 프로그램 내에서 본인 PC의 `aseprite.exe` 경로를 지정해주어야 합니다.)*

## 기술 스택 (Tech Stack)
- **Python 3**
- **PyQt6** (GUI)
- **Aseprite CLI & Lua API** (File parsing & modification)
- **Wordninja** (Natural Language Processing for word splitting)
- **TheFuzz** (String matching & Spell checking)
