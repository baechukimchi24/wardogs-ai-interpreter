# 무설치 EXE 빌드 안내

**이 ZIP은 완성 EXE가 아니라 Windows에서 자동으로 EXE를 생성하는 소스/빌드 키트입니다.** 현재 환경은 Linux이므로 Windows 실행 파일을 직접 생성·검증하지 못했습니다.

1. GitHub 저장소에 이 폴더의 **내용물 전체**를 업로드합니다. `.github/workflows/windows-portable.yml` 경로가 보존되어야 합니다.
2. 저장소의 `Actions` → `Build Windows Portable EXE` → `Run workflow`를 실행합니다.
3. Windows 빌드가 성공하면 해당 실행 결과의 `Artifacts`에서 ZIP을 다운로드합니다.
4. 배포 ZIP을 압축 해제하고 `WARDOGS Interpreter.exe`를 더블클릭하면 콘솔 창 없이 실행됩니다. EXE와 `_internal`, `bin` 폴더는 함께 유지해야 합니다.
5. 번역 모델/엔진은 프로그램 안에서 설치합니다. Argos 모델 가중치는 포함하지 않았습니다.
6. Windows 11에서 자막, VAC 출력, 게임 캡처 및 GPU를 검증한 후 GitHub Release에 게시하세요.

주의: GitHub Actions의 Windows 러너에선 빌드 결과를 시험 실행해보지 않았습니다. PyInstaller가 수집하지 못한 라이브러리로 실행 오류가 생기면 `logs/app-error.log`를 확인해야 합니다. OPUS-MT 추가 의존성은 기본 EXE에 포함되지 않습니다. 서명되지 않은 앱에 SmartScreen 경고가 나올 수 있고, 외부 라이브러리/모델 라이선스는 배포자가 확인해야 합니다.
