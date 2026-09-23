# ScreenPilot Android

Android Studio Emulator 화면만 보고 정해진 순서대로 조작하는 범용 Python 자동화 도구입니다. 캡처와 입력 모두 ADB를 사용하므로 macOS 마우스 커서를 움직이지 않고, Emulator 창을 foreground로 올리지 않습니다. Chrome이나 VS Code를 사용하는 동안에도 Emulator가 실행 중이고 ADB 연결이 유지되면 계속 동작합니다.

이 프로젝트는 본인이 소유한 앱/게임의 QA와 자동화 탐지 검증용입니다. 화면 기반 정상 입력 자동화까지만 제공하며, 안티치트 무력화·은폐·후킹·프로세스 조작·탐지 신호 위조 기능은 포함하지 않습니다. 방어 성능 평가는 서버/클라이언트 로그와 이 도구의 실행 시각을 별도로 비교하는 방식으로 수행하세요.

## 동작 방식

1. `adb exec-out screencap -p`로 Emulator framebuffer의 PNG를 받습니다.
2. OpenCV 템플릿 매칭으로 YAML에 등록한 요소를 찾습니다.
3. 찾은 사각형의 중심이나 상대 오프셋을 계산합니다.
4. `adb shell input tap/swipe/keyevent`로 Android에 입력합니다.

절대 픽셀 좌표는 템플릿 검출에 사용하지 않습니다. 직접 좌표가 필요한 작업도 화면 너비/높이의 `0..1` 비율로 정의합니다. 각 템플릿은 여러 크기로 검사할 수 있고, 검색 영역(ROI)도 정규화 좌표로 제한할 수 있습니다.

## macOS 설치

요구 사항은 macOS, Python 3.11~3.13, Android SDK Platform-Tools, 실행 중인 Android Studio Emulator입니다.

Android Studio의 **SDK Manager → SDK Tools → Android SDK Platform-Tools**를 설치한 뒤 `adb`가 PATH에 없으면 보통 다음 경로를 추가합니다.

```zsh
echo 'export PATH="$PATH:$HOME/Library/Android/sdk/platform-tools"' >> ~/.zshrc
source ~/.zshrc
```

또는 Homebrew를 사용할 수 있습니다.

```zsh
brew install --cask android-platform-tools
```

프로젝트 환경 설치:

```zsh
cd /Users/sehwan/Projects/macro
uv python install 3.13
uv sync --extra dev
```

`uv`가 없다면 Python 3.11~3.13 환경에서 다음을 사용합니다.

```zsh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Emulator를 Android Studio에서 한 번 실행한 뒤 연결을 확인합니다.

```zsh
uv run screenpilot devices
```

여러 기기가 표시되면 워크플로의 `settings.serial` 또는 실행 시 `--serial emulator-5554`를 지정합니다. Emulator가 `offline`이면 재시작하고, `unauthorized`이면 해당 기기의 디버깅 승인을 확인하세요.

## 새 게임 연결

전체 화면을 저장합니다. 이 작업도 창 포커스를 바꾸지 않습니다.

```zsh
uv run screenpilot capture examples/images/full-screen.png --serial emulator-5554
```

미리보기나 이미지 편집기에서 버튼의 **시각적으로 고유한 부분**만 잘라 PNG로 저장합니다. 상태가 다른 버튼(활성/비활성), 언어별 텍스트, 밝기 변화가 크다면 각각 별도 템플릿으로 만드세요. 템플릿 주변의 움직이는 애니메이션이나 넓은 단색 여백은 제외하는 편이 안정적입니다.

`examples/workflow.example.yaml`을 복사하고 이미지 경로와 단계만 바꿉니다.

```zsh
cp examples/workflow.example.yaml my-game.yaml
uv run screenpilot validate my-game.yaml
uv run screenpilot run my-game.yaml --serial emulator-5554
```

중지는 `Ctrl-C`입니다. 검출 실패 시 `artifact_dir`에 마지막 화면이 저장되어 threshold, ROI, scale 범위를 조정할 수 있습니다.

## YAML 형식

```yaml
settings:
  serial: emulator-5554       # 연결이 하나면 생략 가능
  adb_path: adb
  poll_interval: 0.25
  default_timeout: 12
  artifact_dir: artifacts

templates:
  play:
    path: images/play.png
    threshold: 0.88
    scales: [0.70, 1.40, 15]
    roi: [0.05, 0.40, 0.95, 0.95]

steps:
  - wait_for: {template: play, timeout: 20}
  - tap: {template: play, after: 0.8}
  - tap: {template: play, offset: [0.2, 0.0]}
  - tap_at: [0.50, 0.85]
  - swipe: {from: [0.8, 0.7], to: [0.2, 0.7], duration_ms: 350}
  - keyevent: BACK
  - sleep: 0.5
  - screenshot: checkpoint.png
  - repeat:
      count: 3
      steps:
        - tap_at: [0.5, 0.8]
        - sleep: 0.3
```

지원 action:

- `wait_for`: 템플릿이 보일 때까지 대기합니다.
- `tap`: 템플릿을 기다린 뒤 검출 사각형 중심을 누릅니다. `offset`은 템플릿 크기에 대한 상대값입니다.
- `tap_at`: 화면 크기에 대한 정규화 좌표를 누릅니다.
- `swipe`: 정규화된 시작/끝 좌표로 스와이프합니다.
- `keyevent`: Android keycode(예: `BACK`, `HOME`)를 전송합니다.
- `sleep`, `screenshot`, `repeat`: 지연, 증거 화면 저장, 유한 반복입니다.

### 인식 튜닝

- `threshold`: 보통 `0.80~0.95`. 오탐이면 올리고, 미탐이면 조금 내립니다.
- `scales`: `[최소, 최대, 단계 수]`. Emulator DPI/해상도가 바뀌어도 템플릿 크기를 탐색합니다. 범위가 넓을수록 느립니다.
- `roi`: `[left, top, right, bottom]`, 모두 `0..1`. 버튼이 나타나는 영역을 제한하면 속도와 정확도가 좋아집니다.
- 에셋과 실제 화면의 화면 배율/테마/언어가 매우 다르면 각 상태별 템플릿을 준비하세요.

템플릿 매칭은 회전, 심한 원근 변화, 완전히 동적인 요소에는 적합하지 않습니다. 이 경우에도 게임 내부 상태를 읽는 대신 향후 `TemplateMatcher`와 같은 인터페이스로 특징점/OCR 검출기를 추가할 수 있습니다.

## 포커스와 백그라운드 제약

ScreenPilot은 PyAutoGUI, AppleScript 클릭, macOS Accessibility 마우스 이벤트를 사용하지 않습니다. ADB 명령은 특정 Android 디바이스 serial로 직접 전달되므로 현재 macOS 앱의 포커스와 커서는 그대로 유지됩니다.

단, 다음 조건은 Android/호스트 동작에 따른 제약입니다.

- Emulator 프로세스가 실행 중이고 화면이 잠기지 않아야 합니다.
- Android Studio의 **Emulator tool window**가 보이지 않아도 되지만, AVD를 완전히 종료하면 동작하지 않습니다.
- AVD 설정의 절전/화면 꺼짐 또는 호스트 Mac의 잠자기는 캡처/입력을 멈출 수 있습니다.
- 여러 AVD가 있으면 serial을 반드시 고정해 잘못된 대상 조작을 방지하세요.

## 테스트

실제 게임이나 Emulator 없이 합성 이미지와 가짜 디바이스로 핵심 로직을 검사합니다.

```zsh
uv run pytest
uv run ruff check .
```

테스트 범위에는 다중 스케일 템플릿 검출, ROI, 미검출, 검출 중심 탭, 정규화 좌표, swipe, 반복, 설정 검증이 포함됩니다.

## 사용자 코드 확장 지점

프로젝트 고유 코드는 ScreenPilot 핵심 파일을 직접 수정하지 않고 [screenpilot_user/extensions.py](/Users/sehwan/Projects/macro/src/screenpilot_user/extensions.py)에 작성합니다. 안정적인 인터페이스 정의는 [screenpilot/extensions.py](/Users/sehwan/Projects/macro/src/screenpilot/extensions.py)에 있습니다.

두 인터페이스가 제공됩니다.

- `AutomationBackend`: `screenshot`, `tap`, `swipe`, `keyevent` 구현을 교체합니다. 기본 구현은 `AdbDevice`이며, 예제 `CustomBackend`도 현재는 같은 ADB 동작을 그대로 사용합니다.
- `RunObserver`: `run_start`, `action_start`, `match`, `input`, `action_complete`, `run_error`, `run_complete` 이벤트 사본을 받습니다. 입력 흐름을 변경하지 않고 로그·측정·서버 로그 연계에 사용합니다.

워크플로에서 Python 클래스 경로와 생성자 옵션을 지정합니다.

```yaml
settings:
  backend:
    class: screenpilot_user.extensions.CustomBackend
    options:
      serial: emulator-5554
      adb_path: adb
  observers:
    - class: screenpilot_user.extensions.JsonlObserver
      options:
        path: artifacts/run-events.jsonl
```

`backend`를 생략하면 기존 ADB 구현을 사용합니다. observer는 여러 개 등록할 수 있습니다. 클래스는 ScreenPilot 프로세스와 동일한 권한으로 실행되므로 본인이 검토한 코드만 지정해야 합니다.

사용자 구현 위치는 `CustomBackend`의 메서드입니다.

```python
class CustomBackend:
    def screenshot(self) -> np.ndarray: ...

    def tap(self, x: int, y: int) -> None: ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None: ...

    def keyevent(self, keycode: str) -> None: ...
```

반환되는 screenshot은 OpenCV 형식의 `uint8` BGR 배열이어야 합니다. 좌표는 현재 screenshot의 픽셀 좌표입니다. 우회·은폐 구현은 프로젝트 범위에 포함되지 않으며, 이 확장점은 소유한 테스트 환경의 캡처/입력 어댑터와 관찰 로깅을 분리하기 위한 것입니다.
