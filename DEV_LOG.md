# Aseprite Tag Master - Development Log

이 파일은 AI 개발자(Gemini)와 사용자(SOUTHPAW GAMES)가 함께 "Aseprite Tag Master"를 개발하며 어떤 기능들이 어떻게 구현되었는지 다음 작업 시 참고하기 위해 기록하는 문서입니다.

## 🛠 현재까지 구현된 핵심 기능들 (v1.0)

### 1. 코어 검수 로직 (main.py > format_tag_name)
- **CamelCase/PascalCase 보존**: 기존의 `_` 기준 분리 외에도, 대문자가 섞인 합성어(예: `UltimateAttack`)를 안전하게 분리.
- **Wordninja 연동**: 띄어쓰기 없이 소문자로만 이어진 단어(예: `powerwave`)를 인공지능 모듈(`wordninja`)을 사용해 `PowerWave`로 자동 쪼개기 및 첫 글자 대문자화 지원.
- **스펠링 교정 (Fuzzy Matching)**:
  - `thefuzz` 라이브러리를 사용하여 오타를 자동 교정 (Threshold: 85%).
  - `Die`가 `Dive`로, `Return`이 `Turn`으로 잘못 교정되는 현상을 막기 위해 **"글자 수 차이가 2글자 이상 나면 아예 다른 단어로 취급"**하는 방어 로직 추가.
  - 내장된 **200개 이상의 게임/애니메이션 전문 단어 사전**을 베이스로 사용하여 높은 정확도 보장.

### 2. Aseprite 연동 & 안전성 (Lua Scripting)
- **백그라운드 Lua 실행**: Python이 임시 `.lua` 스크립트를 생성하고, `aseprite.exe -b` 명령어로 호출하여 파일을 읽고 씁니다. 파일 손상(Binary corruption) 확률 0%.
- **Loop 태그 처리**: 태그 이름에 `_(Loop)`가 포함되어 있다면, Aseprite 태그 속성의 Repeat 횟수를 **`1`**로 강제 세팅하는 로직 적용.
- **자동 원본 백업**: 수정을 적용하기 직전, 원본 `.ase` 파일을 파일이 위치한 곳의 `.aseprite_backup/` 이라는 숨김 폴더에 자동 복사(`shutil.copy2`)하여 영구적인 데이터 유실 방지.

### 3. 사용자 인터페이스 (PyQt6)
- **모던 다크 테마 적용 (QSS)**: 전체 UI를 어두운 회색 계열과 눈에 띄는 스카이블루/코랄 색상으로 세련되게 디자인.
- **폴더 단위 드래그 앤 드롭**: 파일뿐만 아니라 **캐릭터 폴더 자체를 드롭**하면 `os.walk`를 이용해 하위 경로의 모든 `.ase` 파일을 자동으로 찾아 리스트에 추가.
- **다중 일괄 단어 치환**: 여러 개의 단어를 동시에 찾고 바꿀 수 있는 동적 테이블(Table) UI 구현. 
- **글자 잘림 버그 완벽 수정**: 검수 리포트 창 등에서 글자를 드래그하거나 복사(Ctrl+C)할 때 글씨가 잘리지 않도록 행(Row)의 기본 높이(`defaultSectionSize`)를 넉넉하게 35~40px로 세팅.

## 📦 빌드 환경 (PyInstaller)
- `pyinstaller --noconsole --onefile` 명령어로 단일 `.exe` 생성.
- `wordninja` 모듈이 의존하는 `wordninja_words.txt.gz` 파일을 `--add-data` 옵션으로 패키지 내부에 강제 포함시켜서, 다른 PC로 `.exe` 하나만 넘겨도 문제없이 구동되도록 세팅 완료.

## 🚀 다음 개발 시 참고할 만한 아이디어 (Future Works)
- UI에서 작성한 치환 규칙(Find & Replace)을 로컬 `.json` 프리셋으로 저장하고 불러오는 기능 추가
- 빈 프레임(Empty frames) 탐지 기능 추가
- 지정된 규칙에 따른 태그별 색상(Tag Color) 자동 지정
